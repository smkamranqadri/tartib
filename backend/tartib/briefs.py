"""Space summary and per-space AI briefs. Briefs are cached by a fingerprint of the space's
items and regenerated only when something in the space changed, or on explicit refresh."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from tartib.ask import AskError, answer_from_rows
from tartib.auth import require_auth
from tartib.clock import today_in, utcnow, utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.sessions import space_counts_today
from tartib.store import list_spaces, serialize_item

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

BRIEF_QUESTION = (
    "Summarise the current state of this space: what's open, what's overdue, what was"
    " decided or noted recently. Max 5 lines."
)
BRIEF_NOTES = 15


def brief_question(conn: sqlite3.Connection, space: str, settings: Settings) -> str:
    """The fixed question, plus today's pomodoro count when there is one. A fact for the
    summary to use, not an instruction: the prompt itself stays as written."""
    sessions = space_counts_today(conn, settings, utcnow()).get(space, 0)
    if not sessions:
        return BRIEF_QUESTION
    much = "1 pomodoro session" if sessions == 1 else f"{sessions} pomodoro sessions"
    return f"{BRIEF_QUESTION} Today the user spent {much} on this space."


BRIEF_MAX_ITEMS = 30
UNFILED = "unfiled"


@router.get("/spaces/summary")
def spaces_summary(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    """One row per configured space plus Unfiled, sorted by last activity."""
    today = today_in(settings.zone, utcnow()).isoformat()
    rows = conn.execute(
        """
        SELECT space,
               SUM(shape = 'task' AND status = 'open' AND stage = 'filed') AS open,
               SUM(shape = 'note') AS notes,
               SUM(shape = 'task' AND status = 'open' AND due IS NOT NULL AND due < ?) AS overdue,
               MAX(updated_at) AS last_activity,
               COUNT(*) AS total
        FROM items GROUP BY space
        """,
        (today,),
    ).fetchall()
    by_space = {r["space"]: r for r in rows}

    def entry(name: str, key: str | None, unfiled: bool = False) -> dict:
        r = by_space.get(key)
        return {
            "name": name,
            "unfiled": unfiled,
            "open": int(r["open"] or 0) if r else 0,
            "notes": int(r["notes"] or 0) if r else 0,
            "overdue": int(r["overdue"] or 0) if r else 0,
            "total": int(r["total"] or 0) if r else 0,
            "last_activity": r["last_activity"] if r else None,
        }

    configured = list_spaces(conn)
    entries = [entry(s, s) for s in configured]
    # newest activity first; spaces with no activity keep their table order at the end
    active = sorted(
        [e for e in entries if e["last_activity"]], key=lambda e: e["last_activity"], reverse=True
    )
    spaces = active + [e for e in entries if not e["last_activity"]]
    return {"spaces": spaces, "unfiled": entry(UNFILED, None, unfiled=True)}


def fingerprint(conn: sqlite3.Connection, space: str, settings: Settings) -> str:
    """Changes when an item is added to (or removed from) the space, and when today's session
    count for it changes. Edits, done ticks, and stars do not regenerate the brief; the refresh
    icon does. Tomorrow's zero also counts as a change, which is what stops a brief carrying
    yesterday's "3 sessions today" into today."""
    row = conn.execute(
        "SELECT COUNT(*), COALESCE(MAX(id), 0) FROM items WHERE space = ?", (space,)
    ).fetchone()
    sessions = space_counts_today(conn, settings, utcnow()).get(space, 0)
    return f"{row[0]}:{row[1]}:{sessions}"


def brief_rows(conn: sqlite3.Connection, space: str) -> list[sqlite3.Row]:
    tasks = conn.execute(
        "SELECT * FROM items WHERE space = ? AND shape = 'task' AND status = 'open'"
        " AND stage = 'filed' ORDER BY starred DESC, due IS NULL, due, id DESC",
        (space,),
    ).fetchall()
    notes = conn.execute(
        "SELECT * FROM items WHERE space = ? AND shape = 'note' ORDER BY id DESC LIMIT ?",
        (space, BRIEF_NOTES),
    ).fetchall()
    return (tasks + notes)[:BRIEF_MAX_ITEMS]


def _cached(conn: sqlite3.Connection, space: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM briefs WHERE space = ?", (space,)).fetchone()


def _shape(conn: sqlite3.Connection, row: sqlite3.Row, fresh: bool) -> dict:
    ids = json.loads(row["item_ids"])
    items = []
    for i in ids:
        r = conn.execute("SELECT * FROM items WHERE id = ?", (i,)).fetchone()
        if r is not None:
            items.append(serialize_item(r))
    return {
        "space": row["space"],
        "text": row["text"],
        "item_ids": ids,
        "items": items,
        "updated_at": row["created_at"],
        "fresh": fresh,
    }


@router.get("/spaces/{space}/brief")
async def space_brief(
    space: str,
    refresh: bool = Query(default=False),
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    space = space.strip().lower()
    if space not in list_spaces(conn):
        raise HTTPException(status_code=404, detail="unknown space")
    fp = fingerprint(conn, space, settings)
    cached = _cached(conn, space)
    if cached is not None and not refresh and cached["fingerprint"] == fp:
        return _shape(conn, cached, fresh=False)

    rows = brief_rows(conn, space)
    if not rows:
        text, ids = "Nothing here yet.", []
    else:
        if not settings.ai_enabled:
            raise HTTPException(status_code=503, detail="AI not configured")
        try:
            result = await answer_from_rows(brief_question(conn, space, settings), rows, settings)
        except AskError as e:
            raise HTTPException(status_code=502, detail=f"brief failed: {e}") from e
        text, ids = result["answer"], result["item_ids"]
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO briefs (space, fingerprint, text, item_ids, created_at) VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT(space) DO UPDATE SET fingerprint = excluded.fingerprint,"
        " text = excluded.text, item_ids = excluded.item_ids, created_at = excluded.created_at",
        (space, fp, text, json.dumps(ids), now),
    )
    conn.commit()
    return _shape(conn, _cached(conn, space), fresh=True)
