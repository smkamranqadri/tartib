"""Background classification. The database is the queue: any capture still `pending` is work."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3

from tartib import db
from tartib.ask import AskError, answer_question
from tartib.classify import ClassifyError, Context, Proposal, classify
from tartib.clock import utcnow, utcnow_iso
from tartib.codex import CodexConfig
from tartib.config import Settings
from tartib.store import SpaceError, insert_item

log = logging.getLogger("tartib.runner")


class Runner:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None

    def enqueue(self, capture_id: int) -> None:
        """Safe to call from request handlers running in the threadpool."""
        if self._loop is None:
            return
        self._loop.call_soon_threadsafe(self.queue.put_nowait, capture_id)

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        for capture_id in await asyncio.to_thread(self._pending_ids):
            self.queue.put_nowait(capture_id)
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
            capture_id = await self.queue.get()
            try:
                await self.process(capture_id)
            except Exception:
                log.exception("classification crashed for capture %s", capture_id)
                await asyncio.to_thread(self._fallback, capture_id, "internal error, see logs")
            finally:
                self.queue.task_done()

    async def process(self, capture_id: int) -> None:
        loaded = await asyncio.to_thread(self._load, capture_id)
        if loaded is None:
            return
        text, created_at = loaded
        s = self.settings
        if not s.ai_enabled:
            await asyncio.to_thread(self._fallback, capture_id, "AI not configured")
            return
        context = Context(
            now=utcnow().astimezone(s.zone),
            zone=s.zone,
            spaces=list(s.spaces),
            codex=CodexConfig(command=s.ai_command, model=s.ai_model, timeout=s.ai_timeout),
        )
        try:
            proposals = await classify(text, context)
        except ClassifyError as e:
            await asyncio.to_thread(self._fallback, capture_id, str(e))
            return
        await asyncio.to_thread(self._apply, capture_id, text, created_at, proposals)
        questions = [p for p in proposals if p.shape == "question"]
        if questions:
            question = questions[0].text if len(proposals) > 1 and questions[0].text else text
            await self._answer(capture_id, question)
        await asyncio.to_thread(self._finish, capture_id, "done", None)

    async def _answer(self, capture_id: int, question: str) -> None:
        conn = self._connect()
        try:
            try:
                result = await answer_question(conn, question, None, self.settings)
                payload = {k: result[k] for k in ("answer", "item_ids")}
                payload["items"] = result["items"]
                conn.execute(
                    "UPDATE captures SET answer_json = ? WHERE id = ?",
                    (json.dumps(payload), capture_id),
                )
            except AskError as e:
                conn.execute(
                    "UPDATE captures SET answer_json = ?, error = ? WHERE id = ?",
                    (
                        json.dumps(
                            {"answer": f"Could not answer: {e}", "item_ids": [], "items": []}
                        ),
                        f"ask failed: {e}",
                        capture_id,
                    ),
                )
            conn.commit()
        finally:
            conn.close()

    # --- sync DB helpers, run in the threadpool ---

    def _connect(self) -> sqlite3.Connection:
        return db.connect(self.settings.db_path)

    def _pending_ids(self) -> list[int]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT id FROM captures WHERE status = 'pending' ORDER BY id"
            ).fetchall()
            return [r["id"] for r in rows]
        finally:
            conn.close()

    def _load(self, capture_id: int) -> tuple[str, str] | None:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT raw_text, created_at, status FROM captures WHERE id = ?", (capture_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None
            return row["raw_text"], row["created_at"]
        finally:
            conn.close()

    def _finish(self, capture_id: int, status: str, error: str | None) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "UPDATE captures SET status = ?, error = COALESCE(?, error), classified_at = ?"
                " WHERE id = ?",
                (status, error, utcnow_iso(), capture_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _fallback(self, capture_id: int, error: str) -> None:
        """No usable proposal: one plain note waits for a human, the error kept on both rows."""
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT raw_text, created_at, status FROM captures WHERE id = ?", (capture_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return
            insert_item(
                conn,
                capture_id=capture_id,
                raw_text=row["raw_text"],
                created_at=row["created_at"],
                fields={"shape": "note", "space": None},
                stage="attention",
                allowed=self.settings.spaces,
                proposal_error=error,
            )
            conn.execute(
                "UPDATE captures SET status = 'error', error = ?, classified_at = ? WHERE id = ?",
                (error, utcnow_iso(), capture_id),
            )
            conn.commit()
        finally:
            conn.close()

    def _apply(
        self, capture_id: int, text: str, created_at: str, proposals: list[Proposal]
    ) -> None:
        conn = self._connect()
        try:
            for p in proposals:
                if p.shape == "question":
                    continue
                filed = p.space is not None and p.confidence >= self.settings.autofile_confidence
                fields = p.model_dump(include={"shape", "space", "title", "due", "remind_at"})
                try:
                    insert_item(
                        conn,
                        capture_id=capture_id,
                        raw_text=p.text or text,
                        created_at=created_at,
                        fields=fields,
                        stage="filed" if filed else "attention",
                        allowed=self.settings.spaces,
                        proposal_json=p.model_dump_json(exclude={"text"}),
                    )
                except SpaceError:  # cannot happen after _normalize, but never lose a capture
                    insert_item(
                        conn,
                        capture_id=capture_id,
                        raw_text=p.text or text,
                        created_at=created_at,
                        fields={**fields, "space": None},
                        stage="attention",
                        allowed=self.settings.spaces,
                        proposal_json=p.model_dump_json(exclude={"text"}),
                    )
            conn.commit()
        finally:
            conn.close()
