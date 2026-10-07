"""Owner-authored descriptions for spaces, with shared validation and stale-write protection."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from unicodedata import category

MAX_DESCRIPTION = 500


class DescriptionError(ValueError):
    """Invalid description data or a failed optimistic write."""


class UnknownSpace(DescriptionError):
    pass


class StaleDescription(DescriptionError):
    pass


def normalize_description(value: str) -> str:
    if not isinstance(value, str):
        raise DescriptionError("description must be text")
    text = value.replace("\r\n", "\n").replace("\r", "\n").strip()
    if len(text) > MAX_DESCRIPTION:
        raise DescriptionError("description must be 500 characters or fewer")
    if any(category(ch) == "Cc" and ch != "\n" for ch in text):
        raise DescriptionError("description contains an unsupported control character")
    return text


def space_description(conn: sqlite3.Connection, name: str) -> dict[str, str] | None:
    row = conn.execute(
        "SELECT description, description_updated_at AS updated_at FROM spaces WHERE name = ?",
        (name,),
    ).fetchone()
    return dict(row) if row else None


def set_space_description(
    conn: sqlite3.Connection, name: str, description: str, updated_at: str
) -> dict[str, str]:
    """CAS under a write lock; every accepted write gets a strictly newer millisecond token."""
    clean = normalize_description(description)
    conn.execute("BEGIN IMMEDIATE")
    try:
        row = conn.execute(
            "SELECT description_updated_at FROM spaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            raise UnknownSpace("unknown space")
        prior = row["description_updated_at"]
        if updated_at != prior:
            raise StaleDescription(
                "This description changed elsewhere. Review the latest version before saving."
            )
        current = datetime.now(UTC)
        now = current.replace(microsecond=(current.microsecond // 1000) * 1000)
        next_time = (
            max(
                now,
                datetime.fromisoformat(prior.replace("Z", "+00:00")) + timedelta(milliseconds=1),
            )
            if prior
            else now
        )
        token = next_time.isoformat(timespec="milliseconds").replace("+00:00", "Z")
        changed = conn.execute(
            "UPDATE spaces SET description = ?, description_updated_at = ? "
            "WHERE name = ? AND description_updated_at = ?",
            (clean, token, name, updated_at),
        )
        if changed.rowcount != 1:
            raise StaleDescription(
                "This description changed elsewhere. Review the latest version before saving."
            )
        conn.commit()
        return {"name": name, "description": clean, "updated_at": token}
    except Exception:
        conn.rollback()
        raise
