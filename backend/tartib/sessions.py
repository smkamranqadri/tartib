"""Pomodoro sessions: the row that outlives the tab, and the push at the end.

The browser only renders a countdown. The truth is a row here, so closing the tab or locking
the phone loses nothing and the outcome sheet is waiting on the next load. Rule 4 allows the
logging and forbids everything built on top of it: no charts, no streaks, no history screen.
"""

from __future__ import annotations

import asyncio
import logging
import sqlite3
from datetime import datetime, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from tartib import db, push
from tartib.auth import require_auth
from tartib.clock import as_utc_iso as iso
from tartib.clock import parse_iso, today_in, utcnow, utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.store import list_spaces, update_fields

log = logging.getLogger("tartib.sessions")

# A "your session ended" push is worth sending for a few minutes. A container that was down
# must not announce, on boot, a session that ended hours ago.
PUSH_GRACE = timedelta(minutes=5)
# How long an unanswered outcome sheet keeps following you. Being asked about a session from
# two days ago is an ambush, not a question.
OUTCOME_WINDOW = timedelta(hours=12)

Outcome = Literal["done", "unfinished", "abandoned"]

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def serialize(row: sqlite3.Row) -> dict:
    return dict(row)


def fetch(conn: sqlite3.Connection, session_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="session not found")
    return row


def running(conn: sqlite3.Connection, now: datetime) -> sqlite3.Row | None:
    """The one counting down. Only this blocks starting another."""
    return conn.execute(
        "SELECT * FROM sessions WHERE outcome IS NULL AND ended_at IS NULL AND ends_at > ?"
        " ORDER BY id DESC LIMIT 1",
        (iso(now),),
    ).fetchone()


def awaiting(conn: sqlite3.Connection, now: datetime) -> sqlite3.Row | None:
    """Finished, and still owed an outcome. Does not stop you starting the next one.

    Finished means either its time ran out or it was stopped by hand, and a stopped session
    has an `ends_at` still in the future -- which is why the window is measured from when it
    actually ended rather than from when it was going to."""
    return conn.execute(
        "SELECT * FROM sessions WHERE outcome IS NULL"
        " AND (ended_at IS NOT NULL OR ends_at <= ?)"
        " AND COALESCE(ended_at, ends_at) > ?"
        " ORDER BY id DESC LIMIT 1",
        (iso(now), iso(now - OUTCOME_WINDOW)),
    ).fetchone()


def close_finished(conn: sqlite3.Connection, now: datetime) -> int:
    """Stamp `ended_at` on sessions whose time ran out while nothing was watching."""
    cur = conn.execute(
        "UPDATE sessions SET ended_at = ends_at WHERE ended_at IS NULL AND ends_at <= ?",
        (iso(now),),
    )
    conn.commit()
    return cur.rowcount


def start(
    conn: sqlite3.Connection, settings: Settings, item_id: int | None, now: datetime
) -> sqlite3.Row:
    if running(conn, now) is not None:
        raise HTTPException(status_code=409, detail="a session is already running")
    if item_id is not None:
        item = conn.execute("SELECT id FROM items WHERE id = ?", (item_id,)).fetchone()
        if item is None:
            raise HTTPException(status_code=404, detail="item not found")
    ends = now + timedelta(minutes=settings.session_minutes)
    cur = conn.execute(
        "INSERT INTO sessions (item_id, started_at, ends_at, created_at) VALUES (?, ?, ?, ?)",
        (item_id, iso(now), iso(ends), utcnow_iso()),
    )
    conn.commit()
    return fetch(conn, int(cur.lastrowid or 0))


def stop(conn: sqlite3.Connection, session_id: int, now: datetime) -> sqlite3.Row:
    """Stop early. The session is kept, counted, and still owed an outcome."""
    row = fetch(conn, session_id)
    if row["ended_at"] is None:
        conn.execute("UPDATE sessions SET ended_at = ? WHERE id = ?", (iso(now), session_id))
        conn.commit()
    return fetch(conn, session_id)


def set_outcome(conn: sqlite3.Connection, session_id: int, outcome: Outcome) -> sqlite3.Row:
    row = fetch(conn, session_id)
    if row["outcome"] is not None:
        raise HTTPException(status_code=409, detail="this session already has an outcome")
    ended = row["ended_at"] or row["ends_at"]
    conn.execute(
        "UPDATE sessions SET outcome = ?, ended_at = ? WHERE id = ?",
        (outcome, ended, session_id),
    )
    # "Done" means the task is done, through the write path approve and PATCH already use.
    # A session with no task records the outcome and ticks nothing.
    if outcome == "done" and row["item_id"] is not None:
        update_fields(conn, row["item_id"], {"status": "done"}, list_spaces(conn))
    conn.commit()
    return fetch(conn, session_id)


def counts_today(conn: sqlite3.Connection, settings: Settings, now: datetime) -> dict:
    """Today's sessions, in the configured zone. The only thing that reads this table."""
    day = today_in(settings.zone, now)
    start_of_day = datetime.combine(day, datetime.min.time(), tzinfo=settings.zone)
    rows = conn.execute(
        "SELECT item_id, COUNT(*) AS n FROM sessions WHERE started_at >= ? GROUP BY item_id",
        (iso(start_of_day),),
    ).fetchall()
    return {
        "total": sum(r["n"] for r in rows),
        "by_item": {r["item_id"]: r["n"] for r in rows if r["item_id"] is not None},
    }


def space_counts_today(conn: sqlite3.Connection, settings: Settings, now: datetime) -> dict:
    """Today's sessions per space, for the brief. A session with no task has no space."""
    day = today_in(settings.zone, now)
    start_of_day = datetime.combine(day, datetime.min.time(), tzinfo=settings.zone)
    rows = conn.execute(
        "SELECT items.space AS space, COUNT(*) AS n FROM sessions"
        " JOIN items ON items.id = sessions.item_id"
        " WHERE sessions.started_at >= ? AND items.space IS NOT NULL GROUP BY items.space",
        (iso(start_of_day),),
    ).fetchall()
    return {r["space"]: r["n"] for r in rows}


class Sessions:
    """One timer per running session, firing at that session's own end.

    The reminder loop's 60s tick is right for a reminder and wrong here: a pomodoro that
    buzzes fifty seconds after the bar reached zero has told you something false.
    """

    def __init__(self, settings: Settings, sender=None) -> None:
        self.settings = settings
        self._sender = sender
        self._loop: asyncio.AbstractEventLoop | None = None
        self._timers: dict[int, asyncio.Task[None]] = {}

    @property
    def sender(self):
        return self._sender or push.send

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        # A one-shot task does not survive a restart; anything still running gets a new one.
        for session_id, ends_at in await asyncio.to_thread(self._unfinished):
            self._arm(session_id, ends_at)

    async def stop(self) -> None:
        for task in list(self._timers.values()):
            task.cancel()
        self._timers.clear()
        self._loop = None

    def arm(self, session_id: int, ends_at: str) -> None:
        """Safe to call from a request handler running in the threadpool."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._arm, session_id, ends_at)

    def disarm(self, session_id: int) -> None:
        """A session stopped by hand must not buzz at the time it would have ended."""
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._cancel, session_id)

    def _arm(self, session_id: int, ends_at: str) -> None:
        self._cancel(session_id)
        self._timers[session_id] = asyncio.create_task(self._wait(session_id, ends_at))

    def _cancel(self, session_id: int) -> None:
        task = self._timers.pop(session_id, None)
        if task is not None:
            task.cancel()

    async def _wait(self, session_id: int, ends_at: str) -> None:
        try:
            delay = (parse_iso(ends_at) - utcnow()).total_seconds()
            if delay > 0:
                await asyncio.sleep(delay)
            await asyncio.to_thread(self.fire, session_id)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("session %s failed to finish", session_id)
        finally:
            self._timers.pop(session_id, None)

    def fire(self, session_id: int, now: datetime | None = None) -> bool:
        """End the session and push once. `now` is explicit so tests drive the clock."""
        now = now or utcnow()
        conn = db.connect(self.settings.db_path)
        try:
            row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
            if row is None or row["outcome"] is not None:
                return False
            if row["ended_at"] is not None and row["ended_at"] < row["ends_at"]:
                return False  # stopped by hand before its time
            # Announcing it is its own claim, held on `notified_at`. Closing the row is not:
            # a page that watched its countdown reach zero asks the server straight away, and
            # that read must not take the notification with it.
            cur = conn.execute(
                "UPDATE sessions SET notified_at = ? WHERE id = ? AND notified_at IS NULL",
                (iso(now), session_id),
            )
            conn.execute(
                "UPDATE sessions SET ended_at = ? WHERE id = ? AND ended_at IS NULL",
                (row["ends_at"], session_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                return False  # already announced
            if now > parse_iso(row["ends_at"]) + PUSH_GRACE:
                log.info("session %s ended while nothing was running; not pushing", session_id)
                return False
            title = "Session done"
            if row["item_id"] is not None:
                item = conn.execute(
                    "SELECT title, raw_text FROM items WHERE id = ?", (row["item_id"],)
                ).fetchone()
                if item is not None:
                    title = f"Session done: {item['title'] or item['raw_text'][:60]}"
            payload = {"title": title, "url": "/", "tag": f"session-{session_id}"}
            push.broadcast(conn, payload, self.settings, self.sender)
            return True
        finally:
            conn.close()

    def _unfinished(self) -> list[tuple[int, str]]:
        conn = db.connect(self.settings.db_path)
        try:
            rows = conn.execute(
                "SELECT id, ends_at FROM sessions WHERE outcome IS NULL AND ended_at IS NULL"
            ).fetchall()
            return [(r["id"], r["ends_at"]) for r in rows]
        finally:
            conn.close()


# --- routes ---


class StartBody(BaseModel):
    item_id: int | None = None


class OutcomeBody(BaseModel):
    outcome: Outcome


def scheduler(request: Request) -> Sessions | None:
    return getattr(request.app.state, "sessions", None)


@router.post("/sessions", status_code=201)
def begin(
    body: StartBody | None = None,
    request: Request = None,  # type: ignore[assignment]
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Start one. 409 while another is running: one at a time, by design."""
    now = utcnow()
    row = start(conn, settings, body.item_id if body else None, now)
    clock = scheduler(request)
    if clock is not None:
        clock.arm(row["id"], row["ends_at"])
    return serialize(row)


@router.get("/sessions/recent")
def recent(
    space: str | None = None,
    limit: int = Query(default=3, ge=1, le=50),
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Finished sessions, newest first, each with what it was about. Scoped to a space when one
    is given -- a space's own sessions, which rule 4 allows since 2026-09-19; still no charts,
    streaks, cycles or totals over time."""
    where = "WHERE s.ended_at IS NOT NULL"
    params: list = []
    if space:
        where += " AND i.space = ?"
        params.append(space.strip().lower())
    rows = conn.execute(
        f"""
        SELECT s.*, i.title AS item_title, i.raw_text AS item_text, i.space AS item_space
        FROM sessions s LEFT JOIN items i ON i.id = s.item_id
        {where}
        ORDER BY s.started_at DESC, s.id DESC LIMIT ?
        """,
        (*params, limit),
    ).fetchall()
    return {"sessions": [dict(r) for r in rows]}


@router.get("/sessions/current")
def current(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    """What the app shows on load: a countdown, an outcome sheet, or neither."""
    now = utcnow()
    live = running(conn, now)
    if live is not None:
        return {"state": "running", "session": serialize(live), "item": _item(conn, live)}
    close_finished(conn, now)
    owed = awaiting(conn, now)
    if owed is not None:
        return {"state": "awaiting", "session": serialize(owed), "item": _item(conn, owed)}
    return {"state": None, "session": None, "item": None}


def _item(conn: sqlite3.Connection, row: sqlite3.Row) -> dict | None:
    if row["item_id"] is None:
        return None
    from tartib.store import serialize_item

    found = conn.execute("SELECT * FROM items WHERE id = ?", (row["item_id"],)).fetchone()
    return serialize_item(found) if found else None


@router.post("/sessions/{session_id}/stop")
def stop_early(
    session_id: int,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Stop before the time is up. Not a delete: the session is kept and still owed an
    outcome, and the push it would have made is called off."""
    row = stop(conn, session_id, utcnow())
    clock = scheduler(request)
    if clock is not None:
        clock.disarm(session_id)
    return serialize(row)


@router.post("/sessions/{session_id}/outcome")
def outcome(
    session_id: int,
    body: OutcomeBody,
    request: Request,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = set_outcome(conn, session_id, body.outcome)
    clock = scheduler(request)
    if clock is not None:
        clock.disarm(session_id)
    return serialize(row)
