"""Background classification. The database is the queue: anything still in `inbox` is pending."""

from __future__ import annotations

import asyncio
import logging
import sqlite3

from tartib import db
from tartib.classify import ClassifyError, Context, Proposal, classify
from tartib.clock import utcnow, utcnow_iso
from tartib.codex import CodexConfig
from tartib.config import Settings
from tartib.store import file_item, list_spaces

log = logging.getLogger("tartib.runner")


class Runner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None

    def enqueue(self, item_id: int) -> None:
        """Safe to call from request handlers running in the threadpool."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self.queue.put_nowait, item_id)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        for item_id in await asyncio.to_thread(self._pending_ids):
            self.queue.put_nowait(item_id)
        self._task = asyncio.create_task(self._consume())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._loop = None

    async def _consume(self) -> None:
        while True:
            item_id = await self.queue.get()
            try:
                await self.process(item_id)
            except Exception:
                log.exception("classification crashed for item %s", item_id)
            finally:
                self.queue.task_done()

    async def process(self, item_id: int) -> None:
        loaded = await asyncio.to_thread(self._load, item_id)
        if loaded is None:
            return
        text, spaces = loaded
        s = self.settings
        if not s.ai_enabled:
            await asyncio.to_thread(self._write_error, item_id, "AI not configured")
            return
        context = Context(
            now=utcnow().astimezone(s.zone),
            zone=s.zone,
            spaces=spaces,
            codex=CodexConfig(command=s.ai_command, model=s.ai_model, timeout=s.ai_timeout),
        )
        try:
            proposal = await classify(text, context)
        except ClassifyError as e:
            await asyncio.to_thread(self._write_error, item_id, str(e))
            return
        await asyncio.to_thread(self._apply, item_id, proposal)

    # --- sync DB helpers, run in the threadpool ---

    def _connect(self) -> sqlite3.Connection:
        return db.connect(self.settings.db_path)

    def _pending_ids(self) -> list[int]:
        conn = self._connect()
        try:
            rows = conn.execute("SELECT id FROM items WHERE stage = 'inbox' ORDER BY id").fetchall()
            return [r["id"] for r in rows]
        finally:
            conn.close()

    def _load(self, item_id: int) -> tuple[str, list[str]] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT raw_text, stage FROM items WHERE id = ?", (item_id,)
            ).fetchone()
            if row is None or row["stage"] != "inbox":
                return None
            return row["raw_text"], list_spaces(conn)
        finally:
            conn.close()

    def _write_error(self, item_id: int, error: str) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE items SET stage = 'attention', proposal_error = ?, classified_at = ?"
                " WHERE id = ? AND stage = 'inbox'",
                (error, utcnow_iso(), item_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _apply(self, item_id: int, proposal: Proposal) -> None:
        conn = self._connect()
        try:
            proposal_json = proposal.model_dump_json()
            if proposal.confidence >= self.settings.autofile_confidence:
                file_item(conn, item_id, proposal.model_dump(), proposal_json=proposal_json)
            else:
                conn.execute(
                    "UPDATE items SET stage = 'attention', proposal_json = ?,"
                    " proposal_error = NULL, classified_at = ?"
                    " WHERE id = ? AND stage = 'inbox'",
                    (proposal_json, utcnow_iso(), item_id),
                )
                conn.commit()
        finally:
            conn.close()
