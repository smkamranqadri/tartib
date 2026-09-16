"""Items: capture, read, edit, and Needs Attention decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from tartib.auth import require_auth
from tartib.clock import utcnow_iso
from tartib.deps import get_db
from tartib.store import file_item, update_fields

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


class EditBody(BaseModel):
    """Every field optional. Only fields present in the request are applied."""

    model_config = ConfigDict(extra="forbid")

    shape: Literal["task", "note"] | None = None
    space: str | None = Field(default=None, min_length=1, max_length=80)
    title: str | None = Field(default=None, max_length=200)
    due: date | None = None
    remind_at: datetime | None = None
    starred: bool | None = None
    status: Literal["open", "done"] | None = None

    def provided(self) -> dict:
        data = self.model_dump(include=self.model_fields_set)
        if "space" in data and data["space"] is not None:
            data["space"] = data["space"].strip().lower() or "inbox"
        if "title" in data and data["title"] is not None:
            data["title"] = data["title"].strip() or None
        return data


@router.patch("/items/{item_id}")
def edit_item(item_id: int, body: EditBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    fetch_item(conn, item_id)
    update_fields(conn, item_id, body.provided())
    conn.commit()
    return serialize(fetch_item(conn, item_id))


def _require_attention(row: sqlite3.Row) -> None:
    if row["stage"] != "attention":
        raise HTTPException(status_code=409, detail="item is not awaiting a decision")


@router.post("/items/{item_id}/approve")
def approve(
    item_id: int, body: EditBody | None = None, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    row = fetch_item(conn, item_id)
    _require_attention(row)
    fields: dict = json.loads(row["proposal_json"]) if row["proposal_json"] else {}
    fields.pop("confidence", None)
    if body is not None:
        fields.update(body.provided())
    file_item(conn, item_id, fields)
    return serialize(fetch_item(conn, item_id))


@router.post("/items/{item_id}/reject")
def reject(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    row = fetch_item(conn, item_id)
    _require_attention(row)
    file_item(conn, item_id, {"shape": "note", "space": "inbox"})
    return serialize(fetch_item(conn, item_id))
