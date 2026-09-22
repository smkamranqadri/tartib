"""Background classification. The database is the queue: any capture still `pending` is work."""

from __future__ import annotations

import asyncio
import json
import logging
import sqlite3
import time

from tartib import db
from tartib.ask import AskError, answer_question
from tartib.classify import ClassifyError, Context, Proposal, classify
from tartib.clock import utcnow, utcnow_iso
from tartib.config import Settings
from tartib.store import (
    Example,
    SpaceContext,
    SpaceError,
    classifier_examples,
    classify_context,
    house_rules,
    insert_item,
    list_spaces,
    record_call,
    save_quota,
    should_file,
    similar_items,
    space_policies,
    wait_reason_for,
)

log = logging.getLogger("tartib.runner")

RETRY_INTERVAL = 15 * 60  # seconds between probes of failed captures
MAX_RETRIES = 3
NOT_CONFIGURED = "AI not configured"


class Runner:
    def __init__(self, settings: Settings, *, retry: bool = True) -> None:
        self.settings = settings
        self.queue: asyncio.Queue[int] = asyncio.Queue()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._task: asyncio.Task[None] | None = None
        self._retry = retry  # False for the reclassify CLI, which picks its own captures
        self._probe: asyncio.Task[None] | None = None

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
        if self._retry and self.settings.ai_enabled:
            self._probe = asyncio.create_task(self._probe_loop())

    async def stop(self) -> None:
        for task in (self._task, self._probe):
            if task is not None:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._probe = None
        self._loop = None

    async def _probe_loop(self) -> None:
        """Every so often, try the failed captures again: an outage ends without telling anyone."""
        while True:
            await asyncio.sleep(RETRY_INTERVAL)
            try:
                await self.retry_failed()
            except Exception:
                log.exception("retry probe failed")

    async def retry_failed(self) -> list[int]:
        """Put retryable failed captures back in the queue. Returns their ids."""
        ids = await asyncio.to_thread(self._reset_failed)
        for capture_id in ids:
            self.queue.put_nowait(capture_id)
        if ids:
            log.info("retrying %d failed capture(s): %s", len(ids), ids)
        return ids

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
        text, created_at, spaces, existing, rules, examples, candidates = loaded
        s = self.settings
        if not s.ai_enabled:
            await asyncio.to_thread(self._fallback, capture_id, NOT_CONFIGURED)
            return
        context = Context(
            now=utcnow().astimezone(s.zone),
            zone=s.zone,
            spaces=spaces,
            codex=s.codex(),
            existing=existing,
            house_rules=rules,
            examples=examples,
            candidates=candidates,
        )
        seen: list = []
        started = time.monotonic()

        def note(usage, quota, shape) -> None:
            seen.append((usage, quota, shape))

        try:
            proposals = await classify(text, context, on_usage=note)
        except ClassifyError as e:
            await asyncio.to_thread(
                self._record, "classify", capture_id, started, None, str(e), e.quota
            )
            await asyncio.to_thread(self._fallback, capture_id, str(e))
            return
        usage, quota, shape = seen[0] if seen else (None, None, None)
        await asyncio.to_thread(
            self._record, "classify", capture_id, started, usage, None, quota, shape
        )
        await asyncio.to_thread(self._apply, capture_id, text, created_at, proposals)
        questions = [p for p in proposals if p.shape == "question"]
        if questions:
            question = questions[0].text if len(proposals) > 1 and questions[0].text else text
            await self._answer(capture_id, question)
        await asyncio.to_thread(self._finish, capture_id, "done", None)
        # A capture just classified, so the classifier is up: whatever failed earlier can go again.
        if self._retry:
            await self.retry_failed()

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

    def _reset_failed(self) -> list[int]:
        """Failed captures that can go again, reset to pending with the attempt counted.

        Only while the one item is still exactly what the fallback wrote -- a note, no space, no
        title, date or reminder, unstarred, open, text as captured. Anything else means a person
        has started on it, and a retry would throw their work away. "AI not configured" is not a
        failure a retry can fix."""
        conn = self._connect()
        try:
            rows = conn.execute(
                """
                SELECT c.id FROM captures c
                WHERE c.status = 'error' AND c.attempts < ? AND COALESCE(c.error, '') != ?
                  AND (SELECT COUNT(*) FROM items i WHERE i.capture_id = c.id) = 1
                  AND EXISTS (
                    SELECT 1 FROM items i WHERE i.capture_id = c.id
                      AND i.stage = 'attention' AND i.shape = 'note' AND i.space IS NULL
                      AND i.title IS NULL AND i.due IS NULL AND i.remind_at IS NULL
                      AND i.starred = 0 AND i.status = 'open' AND i.raw_text = c.raw_text
                      AND i.proposal_json IS NULL AND i.proposal_error IS NOT NULL)
                ORDER BY c.id
                """,
                (MAX_RETRIES, NOT_CONFIGURED),
            ).fetchall()
            ids = [r["id"] for r in rows]
            for capture_id in ids:
                conn.execute("DELETE FROM items WHERE capture_id = ?", (capture_id,))
                conn.execute(
                    "UPDATE captures SET status = 'pending', error = NULL, classified_at = NULL,"
                    " attempts = attempts + 1 WHERE id = ?",
                    (capture_id,),
                )
            conn.commit()
            return ids
        finally:
            conn.close()

    def _load(
        self, capture_id: int
    ) -> (
        tuple[str, str, list[str], tuple[SpaceContext, ...], str, tuple[Example, ...], tuple]
        | None
    ):
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT raw_text, created_at, status FROM captures WHERE id = ?", (capture_id,)
            ).fetchone()
            if row is None or row["status"] != "pending":
                return None
            return (
                row["raw_text"],
                row["created_at"],
                list_spaces(conn),
                classify_context(conn),
                house_rules(conn),
                classifier_examples(conn, threshold=self.settings.autofile_confidence)[0],
                similar_items(conn, row["raw_text"]),
            )
        finally:
            conn.close()

    def _record(
        self,
        kind: str,
        capture_id: int | None,
        started: float,
        usage,
        failure: str | None,
        quota=None,
        shape=None,
    ) -> None:
        """One row per call, on its own connection. Neither write raises."""
        conn = self._connect()
        try:
            save_quota(conn, quota)
            record_call(
                conn,
                kind=kind,
                model=self.settings.ai_model,
                usage=usage,
                capture_id=capture_id,
                duration_ms=int((time.monotonic() - started) * 1000),
                failure=failure,
                shape=shape,
            )
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
                allowed=list_spaces(conn),
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
            policies = space_policies(conn)
            for p in proposals:
                if p.shape == "question":
                    continue
                # A proposal that asks you something is waiting on you by definition, whatever
                # its confidence and whatever the space's policy says.
                duplicate_of = int(p.duplicate_of) if p.duplicate_of else None
                # The verdict is recorded either way; only the flag decides whether it holds
                # anything back. Eight seeded cases are not a false-positive rate.
                parked = self.settings.duplicate_park and duplicate_of is not None
                filed = (
                    p.clarify is None
                    and not parked
                    and should_file(
                        p.space, p.confidence, self.settings.autofile_confidence, policies
                    )
                )
                fields = p.model_dump(include={"shape", "space", "title", "due", "remind_at"})
                try:
                    insert_item(
                        conn,
                        capture_id=capture_id,
                        raw_text=p.text or text,
                        created_at=created_at,
                        fields=fields,
                        stage="filed" if filed else "attention",
                        allowed=list_spaces(conn),
                        proposal_json=p.model_dump_json(exclude={"text"}),
                        duplicate_of=duplicate_of,
                        wait_reason=(
                            None
                            if filed
                            else wait_reason_for(p.space, duplicate_of, parked)
                        ),
                    )
                except SpaceError:  # cannot happen after _normalize, but never lose a capture
                    insert_item(
                        conn,
                        capture_id=capture_id,
                        raw_text=p.text or text,
                        created_at=created_at,
                        fields={**fields, "space": None},
                        stage="attention",
                        allowed=list_spaces(conn),
                        proposal_json=p.model_dump_json(exclude={"text"}),
                    )
            conn.commit()
        finally:
            conn.close()
