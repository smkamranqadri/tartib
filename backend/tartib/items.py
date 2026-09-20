"""Items: capture, read, edit, and Needs Attention decisions."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, ConfigDict, Field

from tartib.auth import require_auth
from tartib.classify import ClassifyError, Context, classify
from tartib.clock import utcnow, utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings
from tartib.store import (
    SpaceError,
    capture_by_client_id,
    classify_context,
    create_capture,
    file_item,
    insert_item,
    list_spaces,
    serialize_item,
    should_file,
    space_policies,
    thoughts_for,
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
    # The `updated_at` the editor loaded. Sent by the item editor, not by row toggles: when it
    # no longer matches, someone changed the item since -- another device, another tab -- and
    # taking this write would lose theirs without a word.
    expected_updated_at: str | None = Field(default=None, max_length=40)

    def provided(self) -> dict:
        data = self.model_dump(include=self.model_fields_set - {"expected_updated_at"})
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


class DirectBody(BaseModel):
    """An item filed by hand: shape and space already known, so no classifier."""

    model_config = ConfigDict(extra="forbid")

    shape: Literal["task", "note"]
    space: str = Field(max_length=80)
    text: str = Field(min_length=1, max_length=20_000)
    due: date | None = None


@router.post("/items", status_code=201)
def add_item(body: DirectBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """File an item directly. It gets a capture like any other -- what was typed is kept the same
    way -- marked `direct` and already done, so neither the runner nor reclassify touches it."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=422, detail="text is empty")
    fields: dict = {"shape": body.shape, "space": body.space}
    if body.shape == "task" and body.due is not None:
        fields["due"] = body.due

    def go() -> dict:
        now = utcnow_iso()
        cur = conn.execute(
            "INSERT INTO captures (raw_text, source, created_at, status, classified_at, direct)"
            " VALUES (?, 'web', ?, 'done', ?, 1)",
            (text, now, now),
        )
        item_id = insert_item(
            conn,
            capture_id=int(cur.lastrowid or 0),
            raw_text=text,
            created_at=now,
            fields=fields,
            stage="filed",
            allowed=list_spaces(conn),
        )
        conn.commit()
        return serialize_item(fetch_item(conn, item_id))

    try:
        return _write(go)
    except HTTPException:
        conn.rollback()
        raise


@router.patch("/items/{item_id}")
def edit_item(
    item_id: int,
    body: EditBody,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    row = fetch_item(conn, item_id)
    if body.expected_updated_at is not None and row["updated_at"] != body.expected_updated_at:
        raise HTTPException(status_code=409, detail="This item changed since you opened it.")

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


class RedoBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=1, max_length=500)


@router.post("/items/{item_id}/redo")
async def redo(
    item_id: int,
    body: RedoBody,
    conn: sqlite3.Connection = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> dict:
    """Disagree with a proposal and say why: the classifier tries again with the reason. This
    replaced Reject -- a disagreement always gets another attempt, never a discarded proposal.
    The new proposal follows the normal rules, the space's policy included, so a confident one
    files itself. The reason is kept on the item whatever happens next."""
    row = fetch_item(conn, item_id)
    _require_attention(row)
    reason = " ".join(body.reason.split())
    if not reason:
        raise HTTPException(status_code=422, detail="say why")
    if not settings.ai_enabled:
        raise HTTPException(
            status_code=409, detail="The classifier is off, so it cannot try again."
        )
    line = f"{utcnow_iso()[:10]}: {reason}"
    conn.execute(
        "UPDATE items SET feedback = COALESCE(feedback || char(10), '') || ? WHERE id = ?",
        (line, item_id),
    )
    conn.commit()

    earlier = row["proposal_json"] or json.dumps({"shape": row["shape"], "space": row["space"]})
    context = Context(
        now=utcnow().astimezone(settings.zone),
        zone=settings.zone,
        spaces=list_spaces(conn),
        codex=settings.codex(),
        existing=classify_context(conn),
    )
    try:
        proposals = await classify(row["raw_text"], context, correction=(earlier, reason))
    except ClassifyError as e:
        raise HTTPException(status_code=502, detail=f"Could not try again: {e}") from e
    proposal = next((p for p in proposals if p.shape != "question"), None)
    if proposal is None:
        raise HTTPException(status_code=502, detail="The classifier read it as a question.")

    fields = proposal.model_dump(include={"shape", "space", "title", "due", "remind_at"})
    proposal_json = proposal.model_dump_json(exclude={"text"})
    allowed = list_spaces(conn)
    if should_file(
        proposal.space, proposal.confidence, settings.autofile_confidence, space_policies(conn)
    ):
        file_item(conn, item_id, fields, allowed, proposal_json=proposal_json)
    else:
        # Still waiting: every proposal field is replaced, the ones it leaves empty included.
        update_fields(conn, item_id, fields, allowed)
        conn.execute(
            "UPDATE items SET proposal_json = ?, proposal_error = NULL, classified_at = ?"
            " WHERE id = ?",
            (proposal_json, utcnow_iso(), item_id),
        )
        conn.commit()
    return serialize_item(fetch_item(conn, item_id))


class ThoughtBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    body: str = Field(min_length=1, max_length=10_000)


@router.get("/items/{item_id}/thoughts")
def list_thoughts(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """The item's thought log, oldest first."""
    fetch_item(conn, item_id)
    rows = thoughts_for(conn, [item_id]).get(item_id, [])
    return {"thoughts": [dict(r) for r in rows]}


@router.post("/items/{item_id}/thoughts", status_code=201)
def add_thought(
    item_id: int, body: ThoughtBody, conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Append one entry. There is no editing or deleting one: the log is append-only."""
    fetch_item(conn, item_id)
    text = body.body.strip()
    if not text:
        raise HTTPException(status_code=422, detail="the thought is empty")
    cur = conn.execute(
        "INSERT INTO item_thoughts (item_id, body, created_at) VALUES (?, ?, ?)",
        (item_id, text, utcnow_iso()),
    )
    conn.commit()
    row = conn.execute("SELECT * FROM item_thoughts WHERE id = ?", (cur.lastrowid,)).fetchone()
    count = fetch_item(conn, item_id)["thought_count"]
    return {"thought": dict(row), "thought_count": count}


@router.delete("/items/{item_id}")
def delete_item(item_id: int, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Remove the item. Its capture stays, so what was typed is never lost."""
    fetch_item(conn, item_id)
    conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
    conn.commit()
    return {"ok": True, "id": item_id}
