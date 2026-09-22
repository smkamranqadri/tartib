"""Pick for me (slice 32): on demand, the AI stars up to three open tasks to work on next.

A pick is a star with `picked_at` set. The next pick takes those stars back before it gives
new ones; a star a person set -- even on a task Pick chose, once they touch it -- is never
taken (store.update_fields clears the mark). Each pick leaves its reason in the item's thoughts.
Nothing is written unless the model's reply is usable: a failed pick leaves the last one as it was.
"""

from __future__ import annotations

import sqlite3
import time

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tartib.auth import require_auth
from tartib.classify import PromptShape
from tartib.clock import utcnow, utcnow_iso
from tartib.codex import CodexError, run_json
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.queries import today_rows
from tartib.store import item_header, record_call, save_quota, serialize_item

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

MAX_PICKS = 3
MAX_CANDIDATES = 100
EXCERPT = 300  # characters of a task's text below its header
THOUGHT = "Picked for today: "

SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["picks"],
    "properties": {
        "picks": {
            "type": "array",
            "maxItems": MAX_PICKS,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "reason"],
                "properties": {"label": {"type": "string"}, "reason": {"type": "string"}},
            },
        }
    },
}

PROMPT = """You pick what one person should work on next, from their own open tasks below.
Reply with one JSON object only: {{"picks": [{{"label": "t1", "reason": "..."}}]}}.

Rules:
- Pick 1 to {most} tasks from "Candidates", by label. Never pick from "Already on Today".
- Weigh what is overdue or due soon, what has waited longest, and what the person asks for
  below. Together with what is already on Today, the day should be doable.
- "reason" is one short sentence, in plain words, saying why this task and why now.
- Do not run commands or read files.

Current datetime: {now} ({zone})
The person says: {steer}

Already on Today ({today_count}):
{today}

Candidates ({count}):
{candidates}"""


class PickBody(BaseModel):
    steer: str | None = Field(default=None, max_length=300)


def candidates(conn: sqlite3.Connection, exclude: set[int]) -> list[sqlite3.Row]:
    """Open filed tasks not on Today, dated ones first, then the longest untouched."""
    rows = conn.execute(
        "SELECT * FROM items WHERE stage = 'filed' AND shape = 'task' AND status = 'open'"
        " ORDER BY due IS NULL, due, updated_at, id"
    ).fetchall()
    return [r for r in rows if r["id"] not in exclude][:MAX_CANDIDATES]


def build_prompt(
    rows: list[sqlite3.Row], today: list[sqlite3.Row], steer: str, settings: Settings
) -> str:
    def block(row: sqlite3.Row, label: str) -> str:
        text = row["raw_text"].strip()
        if len(text) > EXCERPT:
            text = text[:EXCERPT].rstrip() + "…"
        return f"{item_header(row, label)} · last touched {row['updated_at'][:10]}\n{text}"

    return PROMPT.format(
        most=MAX_PICKS,
        now=utcnow().astimezone(settings.zone).isoformat(),
        zone=settings.tz,
        steer=steer or "(nothing)",
        today_count=len(today),
        today="\n".join(item_header(r) for r in today) or "(nothing)",
        count=len(rows),
        candidates="\n\n".join(block(r, f"t{i}") for i, r in enumerate(rows, 1)),
    )


def chosen(data: dict, rows: list[sqlite3.Row]) -> list[tuple[sqlite3.Row, str]]:
    """The picks the reply names, in its order. Labels are ordinals (slice 28's reasoning): an
    invented one resolves to nothing, so a reply naming nothing real is an unusable reply."""
    by_label = {f"t{i}": r for i, r in enumerate(rows, 1)}
    out: dict[int, tuple[sqlite3.Row, str]] = {}
    for p in data.get("picks") or []:
        if not isinstance(p, dict):
            continue
        row = by_label.get(str(p.get("label") or "").strip())
        reason = " ".join(str(p.get("reason") or "").split())
        if row is not None and reason and row["id"] not in out:
            out[row["id"]] = (row, reason)
    return list(out.values())[:MAX_PICKS]


def apply(
    conn: sqlite3.Connection, picks: list[tuple[sqlite3.Row, str]]
) -> list[tuple[sqlite3.Row, str]]:
    """Take back the last pick's stars and give the new ones, in one transaction. Returns the
    picks actually starred."""
    done = []
    now = utcnow_iso()
    with conn:
        conn.execute("UPDATE items SET starred = 0, picked_at = NULL WHERE picked_at IS NOT NULL")
        for row, reason in picks:
            # Checked again: the model took seconds, and the task may have been finished or
            # deleted meanwhile. Only a task still open is starred and given the reason.
            if conn.execute(
                "UPDATE items SET starred = 1, picked_at = ? WHERE id = ?"
                " AND stage = 'filed' AND shape = 'task' AND status = 'open'",
                (now, row["id"]),
            ).rowcount:
                conn.execute(
                    "INSERT INTO item_thoughts (item_id, body, created_at) VALUES (?, ?, ?)",
                    (row["id"], THOUGHT + reason, now),
                )
                done.append((row, reason))
    return done


@router.post("/pick")
async def pick(
    body: PickBody,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI not configured")
    today, _ = today_rows(conn, settings, utcnow(), without_picks=True)
    rows = candidates(conn, {r["id"] for r in today})
    if not rows:
        return {"picks": [], "message": "Nothing to pick: every open task is already on Today."}
    prompt = build_prompt(rows, today, (body.steer or "").strip(), settings)
    shape = PromptShape(chars=len(prompt), candidates=len(rows))
    started = time.monotonic()

    def record(usage=None, failure: str | None = None, quota=None) -> None:
        save_quota(conn, quota)
        record_call(
            conn,
            kind="pick",
            model=settings.ai_model,
            usage=usage,
            duration_ms=int((time.monotonic() - started) * 1000),
            failure=failure,
            shape=shape,
        )

    try:
        reply = await run_json(prompt, SCHEMA, settings.codex())
    except CodexError as e:
        record(failure=str(e), quota=e.quota)
        raise HTTPException(status_code=502, detail=f"pick failed: {e}") from e
    picks = chosen(reply.data, rows)
    if not picks:
        record(reply.usage, "unusable reply: no pick named a candidate", reply.quota)
        raise HTTPException(status_code=502, detail="pick failed: the reply named no task")
    record(reply.usage, None, reply.quota)
    picks = apply(conn, picks)
    if not picks:
        return {"picks": [], "message": "The tasks it picked changed meanwhile; pick again."}
    fresh = {r["id"]: r for r in conn.execute(
        f"SELECT * FROM items WHERE id IN ({', '.join('?' * len(picks))})",
        [row["id"] for row, _ in picks],
    )}
    return {
        "picks": [
            {"item": serialize_item(fresh[row["id"]]), "reason": reason} for row, reason in picks
        ]
    }
