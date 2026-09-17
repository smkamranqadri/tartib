"""Row helpers and the shared write paths, so the runner and the API file items the same way."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from datetime import UTC, date, datetime

from tartib.clock import utcnow_iso

FILING_FIELDS = ("shape", "space", "title", "due", "remind_at")
EDITABLE_FIELDS = FILING_FIELDS + ("starred", "status", "text")


class SpaceError(ValueError):
    """A space that is not configured, or a missing space where one is required."""


def serialize_item(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["starred"] = bool(item["starred"])
    raw = item.pop("proposal_json", None)
    item["proposal"] = json.loads(raw) if raw else None
    return item


def serialize_capture(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    cap = dict(row)
    raw = cap.pop("answer_json", None)
    cap["answer"] = json.loads(raw) if raw else None
    rows = conn.execute(
        "SELECT * FROM items WHERE capture_id = ? ORDER BY id", (cap["id"],)
    ).fetchall()
    cap["items"] = [serialize_item(r) for r in rows]
    return cap


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


def check_space(space: object, allowed: Sequence[str]) -> str | None:
    if space is None:
        return None
    s = str(space).strip().lower()
    if not s:
        return None
    if s not in allowed:
        raise SpaceError(f"unknown space {s!r}; configured: {', '.join(allowed)}")
    return s


def list_spaces(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM spaces ORDER BY position, name")]


def _clean(fields: dict, allowed: Sequence[str]) -> dict:
    values = {k: to_db_value(k, v) for k, v in fields.items() if k in EDITABLE_FIELDS}
    if "text" in values:
        text = str(values.pop("text") or "").strip()
        if text:
            values["raw_text"] = text
    if "space" in values:
        values["space"] = check_space(values["space"], allowed)
    if values.get("shape") == "note":
        values.update(title=None, due=None, remind_at=None)
    return values


def reconcile_spaces(conn: sqlite3.Connection, allowed: Sequence[str]) -> int:
    """Items whose space is no longer configured go back to Needs Attention with no space.

    Runs at startup so removing a space from TARTIB_SPACES never leaves filed items the UI
    cannot select or filter. Returns how many items moved."""
    placeholders = ", ".join("?" * len(allowed))
    cur = conn.execute(
        f"UPDATE items SET space = NULL, stage = 'attention'"
        f" WHERE space IS NOT NULL AND space NOT IN ({placeholders})",
        list(allowed),
    )
    conn.commit()
    return cur.rowcount


def create_capture(conn: sqlite3.Connection, text: str, source: str) -> int:
    cur = conn.execute(
        "INSERT INTO captures (raw_text, source, created_at) VALUES (?, ?, ?)",
        (text, source, utcnow_iso()),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def insert_item(
    conn: sqlite3.Connection,
    *,
    capture_id: int,
    raw_text: str,
    created_at: str,
    fields: dict,
    stage: str,
    allowed: Sequence[str],
    proposal_json: str | None = None,
    proposal_error: str | None = None,
) -> int:
    values = _clean(fields, allowed)
    if stage == "filed" and not values.get("space"):
        raise SpaceError("a space is required to file an item")
    cols = [
        "capture_id",
        "raw_text",
        "created_at",
        "stage",
        "proposal_json",
        "proposal_error",
        "classified_at",
        *values.keys(),
    ]
    params = [
        capture_id,
        raw_text,
        created_at,
        stage,
        proposal_json,
        proposal_error,
        utcnow_iso(),
        *values.values(),
    ]
    cur = conn.execute(
        f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params
    )
    return int(cur.lastrowid or 0)


def update_fields(
    conn: sqlite3.Connection, item_id: int, fields: dict, allowed: Sequence[str]
) -> None:
    """Apply editable fields. Raises SpaceError for a bad space; the DB rejects filed + null."""
    values = _clean(fields, allowed)
    if not values:
        return
    assignments = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", (*values.values(), item_id))


def file_item(
    conn: sqlite3.Connection,
    item_id: int,
    fields: dict,
    allowed: Sequence[str],
    *,
    proposal_json: str | None = None,
) -> None:
    """Move an item to `filed` with the given fields. A space is required."""
    values = _clean(fields, allowed)
    if not values.get("space"):
        raise SpaceError("a space is required to file an item")
    update_fields(conn, item_id, values, allowed)
    sets = ["stage = 'filed'", "proposal_error = NULL", "classified_at = ?"]
    params: list[object] = [utcnow_iso()]
    if proposal_json is not None:
        sets.append("proposal_json = ?")
        params.append(proposal_json)
    params.append(item_id)
    conn.execute(f"UPDATE items SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()
