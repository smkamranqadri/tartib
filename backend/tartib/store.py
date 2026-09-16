"""Shared write paths so the runner and the API file items the same way."""

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime

from tartib.clock import utcnow_iso

FILING_FIELDS = ("shape", "space", "title", "due", "remind_at")
EDITABLE_FIELDS = FILING_FIELDS + ("starred", "status")


def to_db_value(field: str, value: object) -> object:
    if value is None:
        return None
    if field == "due" and isinstance(value, date):
        return value.isoformat()
    if field == "remind_at" and isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if field == "starred":
        return 1 if value else 0
    return value


def list_spaces(conn: sqlite3.Connection) -> list[str]:
    rows = conn.execute(
        "SELECT space, COUNT(*) AS n FROM items WHERE stage = 'filed'"
        " GROUP BY space ORDER BY n DESC, space"
    ).fetchall()
    return [r["space"] for r in rows]


def update_fields(conn: sqlite3.Connection, item_id: int, fields: dict) -> None:
    """Apply editable fields. A note never carries task fields."""
    values = {k: to_db_value(k, v) for k, v in fields.items() if k in EDITABLE_FIELDS}
    if values.get("shape") == "note":
        values.update(title=None, due=None, remind_at=None)
    if not values:
        return
    assignments = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", (*values.values(), item_id))


def file_item(
    conn: sqlite3.Connection,
    item_id: int,
    fields: dict,
    *,
    proposal_json: str | None = None,
) -> None:
    """Move an item to `filed` with the given fields, keeping the proposal for inspection."""
    update_fields(conn, item_id, fields)
    sets = ["stage = 'filed'", "proposal_error = NULL", "classified_at = ?"]
    params: list[object] = [utcnow_iso()]
    if proposal_json is not None:
        sets.append("proposal_json = ?")
        params.append(proposal_json)
    params.append(item_id)
    conn.execute(f"UPDATE items SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
