"""The reminder loop: one task beside the runner's consumer that pushes reminders the user
set and, once a day, a digest. Nothing else pushes."""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta

from tartib import db, push
from tartib.clock import as_utc_iso as iso
from tartib.clock import today_in, utcnow
from tartib.config import Settings

log = logging.getLogger("tartib.reminders")

INTERVAL = 60.0

# A container that was down overnight must not replay the night when it boots. Anything
# older than this is marked sent without pushing; a reminder is a moment, not a backlog.
GRACE = timedelta(hours=6)
DIGEST_KEY = "digest_date"


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES (?, ?)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def mark_reminded(conn: sqlite3.Connection, item_id: int, remind_at: str, now_iso: str) -> None:
    """`reminded_at` is set once per item, even when every push failed. Retrying next tick
    would nag, and the reminder's moment has passed either way.

    Guarded on the `remind_at` this tick read: a push can take seconds, and if the user moved
    the reminder in that window, marking it sent would swallow the new one for good."""
    conn.execute(
        "UPDATE items SET reminded_at = ? WHERE id = ? AND remind_at = ?",
        (now_iso, item_id, remind_at),
    )
    conn.commit()


def due_items(conn: sqlite3.Connection, now: datetime) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT * FROM items
        WHERE stage = 'filed' AND status = 'open' AND reminded_at IS NULL
          AND remind_at IS NOT NULL AND remind_at <= ? AND remind_at > ?
        ORDER BY remind_at, id
        """,
        (iso(now), iso(now - GRACE)),
    ).fetchall()


def expire_stale(conn: sqlite3.Connection, now: datetime) -> int:
    """Reminders older than the grace window: marked sent, never pushed."""
    cur = conn.execute(
        "UPDATE items SET reminded_at = ? WHERE stage = 'filed' AND status = 'open'"
        " AND reminded_at IS NULL AND remind_at IS NOT NULL AND remind_at <= ?",
        (iso(now), iso(now - GRACE)),
    )
    conn.commit()
    return cur.rowcount


def digest_counts(conn: sqlite3.Connection, settings: Settings, now: datetime) -> tuple[int, int]:
    day = today_in(settings.zone, now).isoformat()
    due = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE stage = 'filed' AND shape = 'task'"
        " AND status = 'open' AND due IS NOT NULL AND due <= ?",
        (day,),
    ).fetchone()["n"]
    waiting = conn.execute("SELECT COUNT(*) AS n FROM items WHERE stage = 'attention'").fetchone()[
        "n"
    ]
    return due, waiting


def digest_due(conn: sqlite3.Connection, settings: Settings, now: datetime) -> str | None:
    """The local date the digest is owed for, or None when it is too early or already sent."""
    local = now.astimezone(settings.zone)
    if local.time() < settings.summary_at:
        return None
    day = local.date().isoformat()
    return None if get_state(conn, DIGEST_KEY) == day else day


class Reminders:
    """Started only when VAPID keys are configured. With push off the loop must not run at
    all: it would mark reminders sent that nobody could ever have received."""

    def __init__(self, settings: Settings, sender=None) -> None:
        self.settings = settings
        self._sender = sender
        self._task: asyncio.Task[None] | None = None

    @property
    def sender(self):
        """Resolved per send, not bound at import, so the transport can be swapped."""
        return self._sender or push.send

    async def start(self) -> None:
        await asyncio.to_thread(self.seed_digest)
        self._task = asyncio.create_task(self._loop())

    def seed_digest(self, now: datetime | None = None) -> bool:
        """A first start after the digest time writes that day off. Installing at 22:00 should
        not greet you with a digest; the next morning's is unaffected."""
        now = now or utcnow()
        conn = db.connect(self.settings.db_path)
        try:
            day = digest_due(conn, self.settings, now)
            if day is None or get_state(conn, DIGEST_KEY) is not None:
                return False
            set_state(conn, DIGEST_KEY, day)
            return True
        finally:
            conn.close()

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _loop(self) -> None:
        while True:
            try:
                await asyncio.to_thread(self.tick)
            except Exception:
                log.exception("reminder tick failed")
            await asyncio.sleep(INTERVAL)

    def tick(self, now: datetime | None = None) -> dict:
        """One pass. `now` is explicit so tests drive the clock instead of waiting on it."""
        now = now or utcnow()
        conn = db.connect(self.settings.db_path)
        try:
            reminded = 0
            # One strike per endpoint per tick, however many notifications this tick sends.
            struck: set[int] = set()
            for row in due_items(conn, now):
                title = row["title"] or row["raw_text"][:80]
                # The tag is per item: a notification replaces only itself, never another
                # task's. Two reminders due in the same tick must both survive.
                payload = {"title": title, "url": "/today", "tag": f"item-{row['id']}"}
                push.broadcast(conn, payload, self.settings, self.sender, struck)
                mark_reminded(conn, row["id"], row["remind_at"], iso(now))
                reminded += 1
            expired = expire_stale(conn, now)
            digest = self._digest(conn, now, struck)
            return {"reminded": reminded, "expired": expired, "digest": digest}
        finally:
            conn.close()

    def _digest(self, conn: sqlite3.Connection, now: datetime, struck: set[int]) -> bool:
        day = digest_due(conn, self.settings, now)
        if day is None:
            return False
        due, waiting = digest_counts(conn, self.settings, now)
        # The date is recorded either way, so a quiet morning does not turn into an
        # afternoon digest the moment something lands.
        set_state(conn, DIGEST_KEY, day)
        if not due and not waiting:
            return False
        title = f"{due} due today, {waiting} need attention"
        payload = {"title": title, "url": "/today", "tag": "digest"}
        push.broadcast(conn, payload, self.settings, self.sender, struck)
        return True
