"""Answer a question from the user's own items. Read-only. Used by POST /api/ask and by the
runner when a capture turns out to be a question."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tartib.auth import require_auth
from tartib.clock import utcnow
from tartib.codex import CodexError, run_json
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.store import item_header, items_by_thoughts, serialize_item, thoughts_for

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


def _fts_term(word: str) -> str | None:
    """One FTS5 term, or None when the word is not worth searching for. Prefix-matched when
    long enough, so 'decide' finds 'decided'."""
    w = word.lower()
    if w in STOPWORDS or len(w) < 2 or (w.isdigit() and len(w) < 4):
        return None
    return f'"{w}"*' if len(w) >= 4 else f'"{w}"'


def retrieval_query(question: str) -> str:
    """OR of the question's own content words."""
    words = dict.fromkeys(w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE))
    return " OR ".join(t for w in words if (t := _fts_term(w)))


def terms_query(terms: Sequence[str]) -> str:
    """OR of terms proposed by the model. Each is cut down to its word characters first, so
    nothing that comes back can be read as FTS5 syntax."""
    out = []
    for term in terms:
        for word in re.findall(r"\w+", str(term), flags=re.UNICODE):
            if t := _fts_term(word):
                out.append(t)
    return " OR ".join(dict.fromkeys(out))


def _space_clause(space: str | None) -> tuple[str, list[object]]:
    if not space:
        return "", []
    return " AND items.space = ?", [space.strip().lower()]


def search(conn: sqlite3.Connection, match: str, space: str | None) -> list:
    """Items matching an FTS5 query, best first, plus any whose thoughts match it."""
    space_sql, params = _space_clause(space)
    rows = conn.execute(
        "SELECT items.* FROM items_fts JOIN items ON items.id = items_fts.rowid"
        f" WHERE items_fts MATCH ?{space_sql} ORDER BY items_fts.rank, items.id DESC LIMIT ?",
        [match, *params, MAX_ITEMS],
    ).fetchall()
    if len(rows) < MAX_ITEMS:  # and what only an item's thoughts mention
        where = [space_sql.removeprefix(" AND ")] if space_sql else []
        rows += items_by_thoughts(
            conn, match, where, params, [r["id"] for r in rows], MAX_ITEMS - len(rows)
        )
    return rows


def more_to_find(conn: sqlite3.Connection, space: str | None, matched_rows: int) -> bool:
    """Whether anything exists beyond what the question's own words actually matched.

    `matched_rows` is 0 when retrieval matched nothing, because the rows it returns then are
    the most recent items rather than answers -- expansion is worth its ~10s against any
    non-empty database. When the words did match, it is worth it only if something is left to
    find: a database holding one item should not spend a call looking for a second.
    """
    space_sql, params = _space_clause(space)
    row = conn.execute(
        f"SELECT COUNT(*) AS n FROM items WHERE 1=1{space_sql}", params
    ).fetchone()
    return int(row["n"]) > matched_rows


def recent(conn: sqlite3.Connection, space: str | None) -> list:
    space_sql, params = _space_clause(space)
    return conn.execute(
        f"SELECT * FROM items WHERE 1=1{space_sql} ORDER BY id DESC LIMIT ?",
        [*params, MAX_ITEMS],
    ).fetchall()


def rows_by_ids(conn: sqlite3.Connection, ids: Sequence[int]) -> list:
    """The given items, in the order asked for. Unknown ids are dropped."""
    wanted = [i for i in dict.fromkeys(ids) if isinstance(i, int)]
    if not wanted:
        return []
    marks = ",".join("?" * len(wanted))
    by_id = {
        r["id"]: r
        for r in conn.execute(f"SELECT * FROM items WHERE id IN ({marks})", wanted).fetchall()
    }
    return [by_id[i] for i in wanted if i in by_id]


def merge(*groups: list) -> list:
    """Groups in order of priority, first occurrence wins, capped at MAX_ITEMS."""
    out: list = []
    seen: set[int] = set()
    for group in groups:
        for row in group:
            if row["id"] in seen:
                continue
            seen.add(row["id"])
            out.append(row)
            if len(out) == MAX_ITEMS:
                return out
    return out


def retrieve(conn: sqlite3.Connection, question: str, space: str | None) -> tuple[list, bool]:
    """Matching items ranked by FTS5, else the most recent ones. Returns (rows, matched)."""
    match = retrieval_query(question)
    if match:
        rows = search(conn, match, space)
        if rows:
            return rows, True
    return recent(conn, space), False


ANSWER_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["answer", "item_ids"],
    "properties": {
        "answer": {"type": "string"},
        "item_ids": {"type": "array", "items": {"type": "integer"}},
    },
}

MIN_ROWS = 3  # fewer matches than this and the question has not really been answered yet
MAX_TERMS = 5

TERMS_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["terms"],
    "properties": {"terms": {"type": "array", "items": {"type": "string"}}},
}

TERMS_PROMPT = """You propose search terms for one person's own notes and tasks.
Reply with one JSON object only: {{"terms": [ ... ]}} -- 3 to 5 single words.

Their question's own words found little or nothing, so propose the words their note would
likely use instead: the everyday word for a formal one, the thing rather than the act, the
name of what the question describes. Single words, no phrases, no punctuation, no repeats of
the question's own words. Do not run commands or read files.

Current datetime: {now} ({zone})
Question: {question}"""


@dataclass(frozen=True)
class Prior:
    """The turn before this one, so a follow-up has something to refer to."""

    question: str
    item_ids: tuple[int, ...] = ()


PRIOR = """
Just before this, you were asked: {question}
You answered from these items, in this order: {ids}.
"the first one", "the second one", "that one" and the like refer to that list.
"""


PROMPT = """You answer one person's question using only their own captured notes and tasks below.
Reply with one JSON object only: {{"answer": string, "item_ids": [integers]}}.

Rules:
- Use only the items below. If they do not contain the answer, say so plainly and return
  an empty "item_ids".
- Quote or closely paraphrase the item text; do not invent details.
- For status questions, state what is open and what is done, using the task status in
  each header. Do not guess dates; "as of" means the current datetime below.
- "item_ids" lists every item you relied on, most relevant first.
- Lines under "Thoughts:" are the person's own dated notes on that item, added later; they are
  part of the item.
- A few sentences, plain text, no markdown. Do not run commands or read files.

Current datetime: {now} ({zone})
{prior}Question: {question}

Items ({count}):
{items}"""


def format_item(row: sqlite3.Row, thoughts: list | None = None) -> str:
    """The header comes from store.item_header, which classify's context block also uses."""
    text = f"{item_header(row)}\n{row['raw_text']}"
    if thoughts:
        text += "\nThoughts:\n" + "\n".join(
            f"- {t['created_at'][:10]}: {t['body']}" for t in thoughts
        )
    return text


def build_prompt(
    question: str,
    rows: list,
    settings: Settings,
    thoughts: dict | None = None,
    prior: Prior | None = None,
) -> str:
    now = utcnow().astimezone(settings.zone)
    block = ""
    if prior and prior.item_ids:
        block = PRIOR.format(
            question=prior.question.strip(),
            ids=", ".join(str(i) for i in prior.item_ids),
        )
    return PROMPT.format(
        now=now.isoformat(),
        zone=settings.tz,
        prior=block,
        question=question.strip(),
        count=len(rows),
        items="\n\n".join(format_item(r, (thoughts or {}).get(r["id"])) for r in rows),
    )


async def expand_terms(question: str, settings: Settings) -> list[str]:
    """Words to search for when the question's own words found nothing.

    A failure here is not a failed question -- the caller keeps whatever the cheap path
    returned -- so CodexError is swallowed rather than raised.
    """
    now = utcnow().astimezone(settings.zone)
    prompt = TERMS_PROMPT.format(
        now=now.isoformat(), zone=settings.tz, question=question.strip()
    )
    try:
        data = await run_json(prompt, TERMS_SCHEMA, settings.codex())
    except CodexError:
        return []
    terms = data.get("terms") or []
    return [str(t).strip() for t in terms if str(t).strip()][:MAX_TERMS]


EMPTY = {
    "answer": "There are no items to answer from yet.",
    "item_ids": [],
    "items": [],
    "matched": False,
    "expanded": False,
}


async def answer_from_rows(
    question: str,
    rows: list,
    settings: Settings,
    thoughts: dict | None = None,
    prior: Prior | None = None,
) -> dict:
    """Ask Codex about exactly these rows (and their thoughts) and shape the reply. Raises
    AskError on failure."""
    try:
        data = await run_json(
            build_prompt(question, rows, settings, thoughts, prior),
            ANSWER_SCHEMA,
            settings.codex(),
        )
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
    }


async def answer_question(
    conn: sqlite3.Connection,
    question: str,
    space: str | None,
    settings: Settings,
    prior: Prior | None = None,
) -> dict:
    """Retrieve, ask Codex, and shape the reply. Raises AskError when Codex fails.

    The second Codex call is spent only where the first retrieval failed: a question whose own
    words already found enough costs exactly one call, as it always did.
    """
    rows, matched = await asyncio.to_thread(retrieve, conn, question, space)
    expanded = False
    thin = not matched or len(rows) < MIN_ROWS
    matched_rows = len(rows) if matched else 0
    if thin and await asyncio.to_thread(more_to_find, conn, space, matched_rows):
        terms = await expand_terms(question, settings)
        match = terms_query(terms) if terms else ""
        found = await asyncio.to_thread(search, conn, match, space) if match else []
        if found:
            # The question's own matches stay in front: they matched the words actually used.
            rows = merge(rows if matched else [], found, [] if matched else rows)
            matched, expanded = True, True
    if prior and prior.item_ids:
        rows = merge(await asyncio.to_thread(rows_by_ids, conn, prior.item_ids), rows)
    if not rows:
        return dict(EMPTY)
    thoughts = await asyncio.to_thread(thoughts_for, conn, [r["id"] for r in rows])
    result = await answer_from_rows(question, rows, settings, thoughts, prior)
    return {**result, "matched": matched, "expanded": expanded}


class AskBody(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    space: str | None = Field(default=None, max_length=80)
    # The turn before this one, sent by the client, which already has it on screen.
    prior_question: str | None = Field(default=None, max_length=2000)
    prior_item_ids: list[int] = Field(default_factory=list, max_length=MAX_ITEMS)


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
    prior = None
    if body.prior_question and body.prior_item_ids:
        prior = Prior(question=body.prior_question, item_ids=tuple(body.prior_item_ids))
    try:
        return await answer_question(conn, question, body.space, settings, prior)
    except AskError as e:
        raise HTTPException(status_code=502, detail=f"ask failed: {e}") from e
