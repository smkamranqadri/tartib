"""Answer a question from the user's own items. Read-only. Used by POST /api/ask and by the
runner when a capture turns out to be a question."""

from __future__ import annotations

import asyncio
import re
import sqlite3

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tartib.auth import require_auth
from tartib.clock import utcnow
from tartib.codex import CodexConfig, CodexError, run_json
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.store import serialize_item

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

MAX_ITEMS = 20

STOPWORDS = frozenset(
    """a about after again all am an and any are as at be because been before being but by
    can could did do does doing down during for from had has have having he her here hers him
    his how i if in into is it its just me more most my no nor not of off on once only or
    other our ours out over own same she should so some such than that the their theirs them
    then there these they this those through to too under until up very was we were what when
    where which while who whom why will with would you your yours decide decided decision
    say said tell told think thought remember note notes wrote write""".split()
)


class AskError(Exception):
    pass


def retrieval_query(question: str) -> str:
    """OR of the question's content words; prefix-match longer ones so 'decide' finds 'decided'."""
    words = [w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE)]
    terms = []
    for w in dict.fromkeys(words):  # unique, ordered
        if w in STOPWORDS or len(w) < 2 or w.isdigit() and len(w) < 4:
            continue
        terms.append(f'"{w}"*' if len(w) >= 4 else f'"{w}"')
    return " OR ".join(terms)


def retrieve(conn: sqlite3.Connection, question: str, space: str | None) -> tuple[list, bool]:
    """Matching items ranked by FTS5, else the most recent ones. Returns (rows, matched)."""
    match = retrieval_query(question)
    params: list[object] = []
    space_sql = ""
    if space:
        space_sql = " AND items.space = ?"
        params.append(space.strip().lower())
    if match:
        rows = conn.execute(
            "SELECT items.* FROM items_fts JOIN items ON items.id = items_fts.rowid"
            f" WHERE items_fts MATCH ?{space_sql} ORDER BY items_fts.rank, items.id DESC LIMIT ?",
            [match, *params, MAX_ITEMS],
        ).fetchall()
        if rows:
            return rows, True
    rows = conn.execute(
        f"SELECT * FROM items WHERE 1=1{space_sql} ORDER BY id DESC LIMIT ?",
        [*params, MAX_ITEMS],
    ).fetchall()
    return rows, False


ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "item_ids"],
    "properties": {
        "answer": {"type": "string"},
        "item_ids": {"type": "array", "items": {"type": "integer"}},
    },
}

PROMPT = """You answer one person's question using only their own captured notes and tasks below.
Reply with one JSON object only: {{"answer": string, "item_ids": [integers]}}.

Rules:
- Use only the items below. If they do not contain the answer, say so plainly and return
  an empty "item_ids".
- Quote or closely paraphrase the item text; do not invent details.
- For status questions, state what is open and what is done, using the task status in
  each header. Do not guess dates; "as of" means the current datetime below.
- "item_ids" lists every item you relied on, most relevant first.
- A few sentences, plain text, no markdown. Do not run commands or read files.

Current datetime: {now} ({zone})
Question: {question}

Items ({count}):
{items}"""


def format_item(row: sqlite3.Row) -> str:
    space = row["space"] or "(none)"
    head = f"[id {row['id']}] {row['created_at'][:10]} · space: {space} · {row['shape']}"
    if row["shape"] == "task":
        head += f": {row['title'] or ''}"
        if row["due"]:
            head += f" · due {row['due']}"
        head += f" · {row['status']}"
    return f"{head}\n{row['raw_text']}"


def build_prompt(question: str, rows: list, settings: Settings) -> str:
    now = utcnow().astimezone(settings.zone)
    return PROMPT.format(
        now=now.isoformat(),
        zone=settings.tz,
        question=question.strip(),
        count=len(rows),
        items="\n\n".join(format_item(r) for r in rows),
    )


EMPTY = {
    "answer": "There are no items to answer from yet.",
    "item_ids": [],
    "items": [],
    "matched": False,
}


async def answer_question(
    conn: sqlite3.Connection, question: str, space: str | None, settings: Settings
) -> dict:
    """Retrieve, ask Codex, and shape the reply. Raises AskError when Codex fails."""
    rows, matched = await asyncio.to_thread(retrieve, conn, question, space)
    if not rows:
        return dict(EMPTY)
    cfg = CodexConfig(
        command=settings.ai_command, model=settings.ai_model, timeout=settings.ai_timeout
    )
    try:
        data = await run_json(build_prompt(question, rows, settings), ANSWER_SCHEMA, cfg)
    except CodexError as e:
        raise AskError(str(e)) from e
    by_id = {r["id"]: r for r in rows}
    raw_ids = data.get("item_ids") or []
    item_ids = [i for i in dict.fromkeys(raw_ids) if isinstance(i, int) and i in by_id]
    answer = str(data.get("answer") or "").strip() or "No answer."
    return {
        "answer": answer,
        "item_ids": item_ids,
        "items": [serialize_item(by_id[i]) for i in item_ids],
        "matched": matched,
    }


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    space: str | None = Field(default=None, max_length=80)


@router.post("/ask")
async def ask(
    body: AskBody,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    if not settings.ai_enabled:
        raise HTTPException(status_code=503, detail="AI not configured")
    question = body.question.strip()
    if not question:
        raise HTTPException(status_code=422, detail="question is empty")
    try:
        return await answer_question(conn, question, body.space, settings)
    except AskError as e:
        raise HTTPException(status_code=502, detail=f"ask failed: {e}") from e
