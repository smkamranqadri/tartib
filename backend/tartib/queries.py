"""Read endpoints behind the three screens."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, time
from typing import Literal

from fastapi import APIRouter, Depends, Query

from tartib.auth import require_auth
from tartib.clock import today_in, utcnow, utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.store import serialize_capture, serialize_item

RECENT_MIN = 3
RECENT_MAX = 20

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


@router.get("/today")
def today(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    """Open tasks due today or earlier, starred, or whose reminder time has passed,
    plus the most recent captures: always the newest 3, extended to everything captured today."""
    now = utcnow()
    today = today_in(settings.zone, now)
    day = today.isoformat()
    rows = conn.execute(
        """
        SELECT * FROM items
        WHERE stage = 'filed' AND shape = 'task' AND status = 'open'
          AND (due <= ? OR starred = 1 OR remind_at <= ?)
        ORDER BY due IS NULL, due, remind_at IS NULL, remind_at, starred DESC, created_at DESC
        """,
        (day, utcnow_iso()),
    ).fetchall()
    start_of_day = (
        datetime.combine(today, time.min, tzinfo=settings.zone).astimezone(UTC).isoformat()
    ).replace("+00:00", "Z")
    recent = conn.execute(
        """
        SELECT * FROM captures
        WHERE id IN (SELECT id FROM captures ORDER BY id DESC LIMIT ?) OR created_at >= ?
        ORDER BY id DESC LIMIT ?
        """,
        (RECENT_MIN, start_of_day, RECENT_MAX),
    ).fetchall()
    return {
        "date": day,
        "items": [serialize_item(r) for r in rows],
        "recent": [serialize_capture(conn, r) for r in recent],
    }


@router.get("/attention")
def attention(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    rows = conn.execute(
        "SELECT * FROM items WHERE stage = 'attention' ORDER BY created_at, id"
    ).fetchall()
    return {"items": [serialize_item(r) for r in rows]}


@router.get("/spaces")
def spaces(settings: Settings = Depends(get_settings)) -> dict:
    return {"spaces": list(settings.spaces)}


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
