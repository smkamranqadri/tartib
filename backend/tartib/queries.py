"""Read endpoints behind the three screens."""

from __future__ import annotations

import sqlite3
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query

from tartib.auth import require_auth
from tartib.clock import today_in, utcnow, utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings, push_ready
from tartib.sessions import counts_today
from tartib.store import list_spaces, serialize_capture, serialize_item

RECENT = 3
RECENT_PAGE = 50
STALE_DAYS = 14

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
    cutoff = (utcnow() - timedelta(days=STALE_DAYS)).isoformat().replace("+00:00", "Z")
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
        # The public key only, and only when a push could actually be delivered. The private
        # one never leaves the process.
        "vapid_public": settings.vapid_public if can_push else None,
    }


@router.get("/recent")
def recent_captures(
    limit: int = Query(default=RECENT_PAGE, ge=1, le=200),
    before: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Captures newest first, keyset-paged by id: pass next_before back as before."""
    if before is None:
        rows = conn.execute(
            "SELECT * FROM captures ORDER BY id DESC LIMIT ?", (limit + 1,)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM captures WHERE id < ? ORDER BY id DESC LIMIT ?", (before, limit + 1)
        ).fetchall()
    has_more = len(rows) > limit
    rows = rows[:limit]
    return {
        "captures": [serialize_capture(conn, r) for r in rows],
        "next_before": rows[-1]["id"] if has_more and rows else None,
    }


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
    has_more = len(rows) > limit
    rows = rows[:limit]
    items = [serialize_item(r) for r in rows]
    next_before = items[-1]["id"] if has_more and not match else None
    return {"items": items, "next_before": next_before}
