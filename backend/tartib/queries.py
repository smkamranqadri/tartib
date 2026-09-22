"""Read endpoints behind the three screens."""

from __future__ import annotations

import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field

from tartib.auth import require_auth
from tartib.clock import today_in, utcnow, utcnow_iso
from tartib.codex import Usage
from tartib.config import Settings
from tartib.deps import get_db, get_settings, push_ready
from tartib.sessions import counts_today
from tartib.store import (
    HOUSE_RULES_MAX,
    STALE_DAYS,
    classifier_examples,
    house_rules,
    items_by_thoughts,
    list_spaces,
    read_quota,
    serialize_capture,
    serialize_item,
    set_house_rules,
    stale_cutoff,
    usage_totals,
)
from tartib.usage import rates_for, refresh

RECENT = 3
RECENT_PAGE = 50

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


@router.get("/today")
def today(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    """Open tasks due today or earlier, starred, whose reminder time has passed, or that you
    have spent a session on today, plus the newest 3 captures.

    A task you are running pomodoros on is today's work whatever its due date says, and it is
    the only place its session count can be shown."""
    now = utcnow()
    today = today_in(settings.zone, now)
    day = today.isoformat()
    counts = counts_today(conn, settings, now)
    worked_on = [int(i) for i in counts["by_item"]]
    placeholders = ", ".join("?" * len(worked_on))
    worked_clause = f" OR items.id IN ({placeholders})" if worked_on else ""
    rows = conn.execute(
        f"""
        SELECT * FROM items
        WHERE stage = 'filed' AND shape = 'task' AND status = 'open'
          AND (due <= ? OR starred = 1 OR remind_at <= ?{worked_clause})
        ORDER BY due IS NULL, due, remind_at IS NULL, remind_at, starred DESC, created_at DESC
        """,
        (day, utcnow_iso(), *worked_on),
    ).fetchall()
    recent = conn.execute("SELECT * FROM captures ORDER BY id DESC LIMIT ?", (RECENT,)).fetchall()
    active = conn.execute(
        "SELECT space FROM items WHERE space IS NOT NULL ORDER BY updated_at DESC, id DESC LIMIT 1"
    ).fetchone()
    return {
        "date": day,
        "items": [serialize_item(r) for r in rows],
        "recent": [serialize_capture(conn, r) for r in recent],
        "active_space": active["space"] if active else None,
        # Today's pomodoros: the total, and per task where one was attached.
        "sessions": counts,
    }


@router.get("/attention")
def attention(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """The decision queue, plus open tasks nobody has touched for STALE_DAYS."""
    rows = conn.execute(
        "SELECT * FROM items WHERE stage = 'attention' ORDER BY created_at, id"
    ).fetchall()
    cutoff = stale_cutoff()
    stale = conn.execute(
        "SELECT * FROM items WHERE stage = 'filed' AND shape = 'task' AND status = 'open'"
        " AND updated_at < ? ORDER BY updated_at, id",
        (cutoff,),
    ).fetchall()
    return {
        "items": [serialize_item(r) for r in rows],
        "stale": [serialize_item(r) for r in stale],
        "stale_days": STALE_DAYS,
    }


@router.get("/config")
def config(
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
    can_push: bool = Depends(push_ready),
) -> dict:
    """What the UI may show about this install."""
    return {
        "tz": settings.tz,
        "spaces": list_spaces(conn),
        "ai": settings.ai_enabled,
        "autofile_confidence": settings.autofile_confidence,
        "house_rules": house_rules(conn),
        "house_rules_max": HOUSE_RULES_MAX,
        # How many of the examples sent to the classifier are real corrections rather than
        # padding. Zero is a fact about the data, not a fault: it means nothing has been
        # overridden yet, so there is nothing to learn from.
        "corrections": classifier_examples(conn, threshold=settings.autofile_confidence)[1],
        # The public key only, and only when a push could actually be delivered. The private
        # one never leaves the process.
        "vapid_public": settings.vapid_public if can_push else None,
    }


class HouseRulesBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(default="", max_length=HOUSE_RULES_MAX * 2)


@router.put("/config/house-rules")
def put_house_rules(
    body: HouseRulesBody, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Replace the owner's filing rules. Empty clears them back to the shipped prompt.

    Nothing here can break classification: the rules are appended to the prompt, never
    substituted into the part that defines the reply format.
    """
    return {"house_rules": set_house_rules(conn, body.text)}


@router.get("/usage")
def ai_usage(
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """What the AI has cost. The money figure is an estimate twice over -- the subscription
    reports no cost at all, and a catalogue price is list price -- and the UI says so."""
    totals = usage_totals(conn)
    refresh(settings.ai_model, settings.db_path)  # at most once a day; failure keeps the cache
    rates = rates_for(settings.ai_model, settings.db_path)
    spent = Usage(
        input_tokens=totals["input_tokens"],
        cached_input_tokens=totals["cached_input_tokens"],
        cache_write_input_tokens=totals["cache_write_input_tokens"],
        output_tokens=totals["output_tokens"],
        reasoning_output_tokens=totals["reasoning_output_tokens"],
        total_tokens=totals["total_tokens"],
    )
    return {
        **totals,
        "cost": round(rates.cost(spent), 6),
        # The arithmetic behind `cost` -- specifically whether reasoning tokens are already
        # inside output_tokens -- has not yet been reconciled against a real call, so the UI
        # does not show it. Slice 29, Still open.
        "cost_verified": False,
        # The last rate-limit reading the CLI gave us. This is the scarce resource, and until
        # now nothing in the app knew it existed.
        "quota": read_quota(conn),
        "model": settings.ai_model,
        "rates": {
            "input": rates.input,
            "output": rates.output,
            "cache_read": rates.cache_read,
            "cache_write": rates.cache_write,
            "source": rates.source,
        },
    }


@router.get("/recent")
def recent_captures(
    limit: int = Query(default=RECENT_PAGE, ge=1, le=200),
    before: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Captures newest first, keyset-paged by id: pass next_before back as before.

    What is waiting in Needs Attention is not repeated here: those items are dropped, and so is
    a capture left with none. A capture with no items at all (still filing, or answered) stays.
    The exclusion is in the SQL so a page is still `limit` long."""
    rows = conn.execute(
        f"""
        SELECT * FROM captures
        WHERE {"id < ? AND" if before is not None else ""}
          (NOT EXISTS (SELECT 1 FROM items WHERE capture_id = captures.id)
           OR EXISTS (SELECT 1 FROM items WHERE capture_id = captures.id AND stage != 'attention'))
        ORDER BY id DESC LIMIT ?
        """,
        (*([before] if before is not None else []), limit + 1),
    ).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    captures = [serialize_capture(conn, r) for r in rows]
    for cap in captures:
        cap["items"] = [i for i in cap["items"] if i["stage"] != "attention"]
    return {"captures": captures, "next_before": rows[-1]["id"] if has_more and rows else None}


def fts_query(q: str) -> str:
    """Turn free text into a safe FTS5 query: quoted tokens, prefix match on the last."""
    tokens = [t.replace('"', '""') for t in q.split() if t.strip()]
    if not tokens:
        return ""
    quoted = [f'"{t}"' for t in tokens]
    quoted[-1] += "*"
    return " ".join(quoted)


@router.get("/items")
def list_items(
    q: str = "",
    space: str | None = None,
    shape: Literal["task", "note"] | None = None,
    status: Literal["open", "done"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    before: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """All items, newest first, or ranked by relevance when `q` is given."""
    where: list[str] = []
    params: list[object] = []
    if space:
        where.append("items.space = ?")
        params.append(space.strip().lower())
    if shape:
        where.append("items.shape = ?")
        params.append(shape)
    if status:
        where.append("items.shape = 'task' AND items.status = ?")
        params.append(status)
    if before is not None:
        where.append("items.id < ?")
        params.append(before)

    match = fts_query(q)
    if match:
        sql = (
            "SELECT items.* FROM items_fts JOIN items ON items.id = items_fts.rowid"
            " WHERE items_fts MATCH ?"
        )
        params.insert(0, match)
        if where:
            sql += " AND " + " AND ".join(where)
        sql += " ORDER BY items_fts.rank, items.id DESC"
    else:
        sql = "SELECT * FROM items"
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += " ORDER BY items.id DESC"
    sql += " LIMIT ?"
    params.append(limit + 1)

    rows = conn.execute(sql, params).fetchall()
    if match and len(rows) <= limit:
        # Then items found through their thoughts, after the ones their own text matched.
        filters = params[1:-1]  # the where-clause values, without the match and the limit
        rows += items_by_thoughts(
            conn, match, where, filters, [r["id"] for r in rows], limit + 1 - len(rows)
        )
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [serialize_item(r) for r in rows]
    next_before = items[-1]["id"] if has_more and not match else None
    return {"items": items, "next_before": next_before}
