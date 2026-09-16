"""Items: capture and read."""

from __future__ import annotations

import json
import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from tartib.auth import require_auth
from tartib.clock import utcnow_iso
from tartib.deps import get_db

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


def serialize(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["starred"] = bool(item["starred"])
    raw = item.pop("proposal_json", None)
    item["proposal"] = json.loads(raw) if raw else None
    return item


def fetch_item(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="item not found")
    return row


class CaptureBody(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)


@router.post("/capture", status_code=201)
def capture(
    body: CaptureBody, request: Request, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    cur = conn.execute(
        "INSERT INTO items (raw_text, created_at) VALUES (?, ?)", (text, utcnow_iso())
    )
    conn.commit()
    item_id = cur.lastrowid
    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        runner.enqueue(item_id)
    return {"id": item_id}


@router.get("/items/{item_id}")
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return serialize(fetch_item(conn, item_id))
