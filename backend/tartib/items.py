"""Items: capture, read, edit, and Needs Attention decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from tartib.auth import require_auth
from tartib.deps import get_db
from tartib.store import (
    SpaceError,
    capture_by_client_id,
    create_capture,
    file_item,
    list_spaces,
    serialize_item,
    update_fields,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

serialize = serialize_item  # kept for callers that import it from here


def fetch_item(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="item not found")
    return row


class CaptureBody(BaseModel):
    text: str = Field(min_length=1, max_length=20_000)
    """Minted by the browser before the first attempt, so a capture that was queued offline and
    sent twice is recognised as the same capture rather than becoming two. Optional: curl and
    the iOS Shortcut send none, and nothing needs them to."""
    client_id: str | None = Field(default=None, min_length=8, max_length=64)


@router.post("/capture", status_code=201)
def capture(
    body: CaptureBody,
    request: Request,
    response: Response,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Store the text as a capture and return its id. Classification runs in the background."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    source = "api" if request.headers.get("authorization", "")[:7].lower() == "bearer " else "web"

    if body.client_id:
        existing = capture_by_client_id(conn, body.client_id)
        if existing is not None:
            # Already here. Not re-enqueued: the first attempt did that, and a capture still
            # pending after a restart is re-queued at startup anyway.
            response.status_code = 200
            return {"id": existing}
    try:
        capture_id = create_capture(conn, text, source, body.client_id)
    except sqlite3.IntegrityError:
        # Two attempts at once, and the other won. The row it made is the answer to both.
        existing = capture_by_client_id(conn, body.client_id) if body.client_id else None
        if existing is None:
            raise
        response.status_code = 200
        return {"id": existing}

    runner = getattr(request.app.state, "runner", None)
    if runner is not None:
        runner.enqueue(capture_id)
    return {"id": capture_id}


@router.get("/items/{item_id}")
def get_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return serialize_item(fetch_item(conn, item_id))


class EditBody(BaseModel):
    """Every field optional. Only fields present in the request are applied."""

    model_config = ConfigDict(extra="forbid")

    shape: Literal["task", "note"] | None = None
    space: str | None = Field(default=None, max_length=80)
    title: str | None = Field(default=None, max_length=200)
    due: date | None = None
    remind_at: datetime | None = None
    starred: bool | None = None
    status: Literal["open", "done"] | None = None
    text: str | None = Field(default=None, min_length=1, max_length=20_000)

    def provided(self) -> dict:
        data = self.model_dump(include=self.model_fields_set)
        if "title" in data and data["title"] is not None:
            data["title"] = data["title"].strip() or None
        return data


def _write(fn) -> dict:
    try:
        return fn()
    except SpaceError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except sqlite3.IntegrityError as e:
        if "space" in str(e).lower() or "CHECK" in str(e):
            raise HTTPException(
                status_code=422, detail="a filed item needs a configured space"
            ) from e
        raise


@router.patch("/items/{item_id}")
def edit_item(
    item_id: int,
    body: EditBody,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    fetch_item(conn, item_id)

    def go() -> dict:
        update_fields(conn, item_id, body.provided(), list_spaces(conn))
        conn.commit()
        return serialize_item(fetch_item(conn, item_id))

    return _write(go)


def _require_attention(row: sqlite3.Row) -> None:
    if row["stage"] != "attention":
        raise HTTPException(status_code=409, detail="item is not awaiting a decision")


@router.post("/items/{item_id}/approve")
def approve(
    item_id: int,
    body: EditBody | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """File the item with its stored proposal, overridden by any fields in the body."""
    row = fetch_item(conn, item_id)
    _require_attention(row)
    fields: dict = json.loads(row["proposal_json"]) if row["proposal_json"] else {}
    fields = {
        k: v for k, v in fields.items() if k in ("shape", "space", "title", "due", "remind_at")
    }
    fields.setdefault("shape", row["shape"])
    if body is not None:
        fields.update(body.provided())
    if not fields.get("space"):
        fields["space"] = row["space"]

    def go() -> dict:
        file_item(conn, item_id, fields, list_spaces(conn))
        return serialize_item(fetch_item(conn, item_id))

    return _write(go)


@router.post("/items/{item_id}/reject")
def reject(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Discard the proposal. The item stays in Needs Attention as a plain note with no space."""
    row = fetch_item(conn, item_id)
    _require_attention(row)
    conn.execute(
        "UPDATE items SET shape = 'note', space = NULL, title = NULL, due = NULL,"
        " remind_at = NULL, proposal_json = NULL, proposal_error = NULL WHERE id = ?",
        (item_id,),
    )
    conn.commit()
    return serialize_item(fetch_item(conn, item_id))


@router.delete("/items/{item_id}")
def delete_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Remove the item. Its capture stays, so what was typed is never lost."""
    fetch_item(conn, item_id)
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return {"ok": True, "id": item_id}
