"""Captures: the stored input. Read endpoint for status, resulting items, and answers."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException

from tartib.auth import require_auth
from tartib.deps import get_db
from tartib.store import serialize_capture

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def fetch_capture(conn: sqlite3.Connection, capture_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM captures WHERE id = ?", (capture_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="capture not found")
    return row


@router.get("/captures/{capture_id}")
def get_capture(capture_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return serialize_capture(conn, fetch_capture(conn, capture_id))
