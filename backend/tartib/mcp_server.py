"""Tartib over MCP (slice 35): agents read and write the owner's items from anywhere.

Served by the app itself at `/mcp`, over MCP's streamable HTTP, **stateless with plain JSON
replies**: Cloudflare sits in front and may buffer a stream, and one request with one answer
needs nothing held open. On only when `TARTIB_MCP_TOKEN` is set; the token is its own, never
the login password, and nothing else is accepted here -- not the browser's cookie either.

Every write goes through the store's own paths (`insert_item`, `update_fields`, the thoughts
insert, `add_space`, the capture path and runner), so titles, links, the touch trigger and
every rule behave exactly as they do from the app. There is no editing of text and no delete,
by the owner's choice. Each capture records the client that wrote it, and the item page shows
"via <client>".
"""

from __future__ import annotations

import hmac
import sqlite3
from datetime import date

from fastapi import HTTPException
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.routing import Route

from tartib import db
from tartib.clock import utcnow_iso
from tartib.config import Settings
from tartib.queries import fts_query
from tartib.spaces import add_space
from tartib.store import (
    insert_item,
    list_spaces,
    serialize_item,
    thoughts_for,
    update_fields,
)
from tartib.store import (
    search as search_items,
)

LIST_LIMIT = 100
MAX_TEXT = 20_000  # the REST API's own cap on an item's text
MIN_TOKEN = 32  # /mcp has no throttle of its own; a long random token is what makes that fine

INSTRUCTIONS = """Tartib is one person's notes and tasks, sorted into spaces.
- Call list_spaces before adding anything, and use a space that exists.
- Never create a space without asking the person first. Suggest the name and wait for a yes.
- Before adding a note or task, search: if the same thing is already there, add a thought to
  it instead of a near-duplicate.
- Name the space when you know it: the item is filed there directly. Without one, Tartib's own
  classifier files it, and it may wait for the person to decide.
- When you finish work on a task, mark it done and add a thought saying what was done.
You cannot edit an item's text or delete anything; the person does that in the app."""


# User-Agents that name an HTTP library, not the agent behind it.
GENERIC_AGENTS = ("python", "httpx", "node", "undici", "axios", "go-http", "curl", "okhttp", "mcp")


def _client(ctx: Context | None) -> str:
    """Who is writing, as a label for the owner to read -- not an identity; the token is that.

    First `?client=` on the URL the client was configured with, the one way to name it that
    works in every client. Then the name from the MCP handshake, which a stateless request only
    carries on the newer protocol. Then the first word of the User-Agent, unless it only names
    an HTTP library. Else "agent"."""
    name = None
    request = getattr(getattr(ctx, "request_context", None), "request", None) if ctx else None
    params = getattr(request, "query_params", None)
    if params is not None:
        name = params.get("client")
    if not name and ctx is not None:
        try:
            info = ctx.session.client_params.client_info
            name = info.name if info else None
        except Exception:  # no session info on this request
            name = None
    if not name and ctx is not None:
        agent = ((ctx.headers or {}).get("user-agent") or "").split("/")[0].split(" ")[0]
        if agent and not agent.lower().startswith(GENERIC_AGENTS):
            name = agent
    name = "".join(ch for ch in (name or "") if ch.isalnum() or ch in "-_.").strip()[:40]
    return name or "agent"


def _date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError as e:
        raise ToolError(f"dates are YYYY-MM-DD, not {value!r}") from e


def _item(row: sqlite3.Row) -> dict:
    """An item as an agent needs it: what it is and where, not the classifier's internals."""
    item = serialize_item(row)
    keep = (
        "id", "space", "shape", "title", "raw_text", "due", "remind_at", "starred", "status",
        "stage", "created_at", "updated_at", "thought_count",
    )
    out = {k: item.get(k) for k in keep}
    out["text"] = out.pop("raw_text")
    return out


def build(app, settings: Settings) -> tuple[MCPServer, Route]:
    """The MCP server and the route that serves it, guarded by the token."""
    server = MCPServer(name="tartib", instructions=INSTRUCTIONS)

    def conn() -> sqlite3.Connection:
        return db.connect(settings.db_path)

    def space_or_fail(c: sqlite3.Connection, space: str) -> str:
        name = (space or "").strip().lower()
        spaces = list_spaces(c)
        if name not in spaces:
            raise ToolError(f"no space {name!r}; spaces are: {', '.join(spaces)}")
        return name

    def fetch(c: sqlite3.Connection, item_id: int) -> sqlite3.Row:
        row = c.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            raise ToolError(f"no item {item_id}")
        return row

    def capture_row(c: sqlite3.Connection, text: str, client: str, direct: bool) -> int:
        now = utcnow_iso()
        cur = c.execute(
            "INSERT INTO captures (raw_text, source, created_at, status, classified_at, direct,"
            " client) VALUES (?, 'api', ?, ?, ?, ?, ?)",
            (text, now, "done" if direct else "pending", now if direct else None,
             1 if direct else 0, client),
        )
        return int(cur.lastrowid or 0)

    def add(shape: str, text: str, space: str | None, due: str | None, ctx: Context | None):
        text = (text or "").strip()
        if not text:
            raise ToolError("the text is empty")
        if len(text) > MAX_TEXT:
            raise ToolError(f"the text is over {MAX_TEXT} characters")
        client = _client(ctx)
        c = conn()
        try:
            if space:
                name = space_or_fail(c, space)
                fields: dict = {"shape": shape, "space": name}
                if shape == "task" and due:
                    fields["due"] = _date(due)
                capture_id = capture_row(c, text, client, direct=True)
                item_id = insert_item(
                    c, capture_id=capture_id, raw_text=text, created_at=utcnow_iso(),
                    fields=fields, stage="filed", allowed=list_spaces(c),
                )
                c.commit()
                return {"filed": True, "item": _item(fetch(c, item_id))}
            # No space: a capture like any other, which the classifier files or leaves waiting.
            capture_id = capture_row(c, text, client, direct=False)
            c.commit()
        finally:
            c.close()
        runner = getattr(app.state, "runner", None)
        if runner is not None:
            runner.enqueue(capture_id)
        return {
            "filed": False,
            "capture_id": capture_id,
            "note": "Sent to Tartib's classifier. It files it, or it waits for the person.",
        }

    # --- reading ---

    @server.tool(
        name="list_spaces", description="The spaces, in the owner's order. Call this before adding."
    )
    def spaces_tool() -> dict:
        c = conn()
        try:
            return {"spaces": list_spaces(c)}
        finally:
            c.close()

    @server.tool(
        name="list_items",
        description=(
            "Filed items in one space: open tasks first (by due date), then done tasks, then "
            "notes, newest first. shape: task|note; status: open|done (tasks only)."
        ),
    )
    def list_items(space: str, shape: str | None = None, status: str | None = None) -> dict:
        c = conn()
        try:
            name = space_or_fail(c, space)
            where, params = ["stage = 'filed'", "space = ?"], [name]
            if shape in ("task", "note"):
                where.append("shape = ?")
                params.append(shape)
            if status in ("open", "done"):
                where.append("shape = 'task' AND status = ?")
                params.append(status)
            rows = c.execute(
                f"SELECT * FROM items WHERE {' AND '.join(where)}"
                " ORDER BY shape = 'note', status = 'done', due IS NULL, due, updated_at DESC"
                " LIMIT ?",
                (*params, LIST_LIMIT),
            ).fetchall()
            return {"space": name, "items": [_item(r) for r in rows]}
        finally:
            c.close()

    @server.tool(
        name="search",
        description="Search items' text and thoughts, best match first; optionally in one space.",
    )
    def search(query: str, space: str | None = None) -> dict:
        c = conn()
        try:
            name = space_or_fail(c, space) if space else None
            match = fts_query(query)
            rows = search_items(c, match, name) if match else []
            return {"items": [_item(r) for r in rows]}
        finally:
            c.close()

    @server.tool(
        name="get_item",
        description="One item with its thoughts (oldest first) and the items that link to it.",
    )
    def get_item(id: int) -> dict:
        from tartib.links import link_view

        c = conn()
        try:
            row = fetch(c, id)
            thoughts = thoughts_for(c, [id]).get(id, [])
            view = link_view(c, row)
            return {
                **_item(row),
                "thoughts": [{"at": t["created_at"], "text": t["body"]} for t in thoughts],
                "links": view["links"],
                "linked_from": [
                    {"id": i["id"], "title": i.get("title") or i["raw_text"].split("\n")[0][:80]}
                    for i in view["linked_from"]
                ],
            }
        finally:
            c.close()

    # --- writing ---

    @server.tool(
        name="add_note",
        description=(
            "Add a note. With a space it is filed there directly; without one Tartib's "
            "classifier files it."
        ),
    )
    def add_note(text: str, space: str | None = None, ctx: Context | None = None) -> dict:
        return add("note", text, space, None, ctx)

    @server.tool(
        name="add_task",
        description=(
            "Add a task; the first line is its title. due is YYYY-MM-DD. With a space it is filed "
            "there directly; without one Tartib's classifier files it and may give it a date."
        ),
    )
    def add_task(
        text: str, space: str | None = None, due: str | None = None, ctx: Context | None = None
    ) -> dict:
        return add("task", text, space, due, ctx)

    @server.tool(
        name="add_thought",
        description="Append a dated thought to an item: what happened, what was decided.",
    )
    def add_thought(id: int, text: str) -> dict:
        body = (text or "").strip()
        if not body:
            raise ToolError("the thought is empty")
        if len(body) > MAX_TEXT:
            raise ToolError(f"the thought is over {MAX_TEXT} characters")
        c = conn()
        try:
            fetch(c, id)
            c.execute(
                "INSERT INTO item_thoughts (item_id, body, created_at) VALUES (?, ?, ?)",
                (id, body, utcnow_iso()),
            )
            c.commit()
            return {"ok": True, "thought_count": fetch(c, id)["thought_count"]}
        finally:
            c.close()

    def edit(id: int, fields: dict, tasks_only: bool = True) -> dict:
        c = conn()
        try:
            row = fetch(c, id)
            if tasks_only and row["shape"] != "task":
                raise ToolError(f"item {id} is a note; this applies to tasks")
            update_fields(c, id, fields, list_spaces(c))
            c.commit()
            return _item(fetch(c, id))
        finally:
            c.close()

    @server.tool(name="set_status", description="Mark a task done or open again.")
    def set_status(id: int, status: str) -> dict:
        if status not in ("done", "open"):
            raise ToolError("status is done or open")
        return edit(id, {"status": status})

    @server.tool(name="set_due", description="Set a task's due date (YYYY-MM-DD); null clears it.")
    def set_due(id: int, due: str | None = None) -> dict:
        return edit(id, {"due": _date(due)})

    @server.tool(name="set_star", description="Star a task, or take its star off.")
    def set_star(id: int, starred: bool) -> dict:
        return edit(id, {"starred": bool(starred)})

    @server.tool(
        name="create_space",
        description=(
            "Create a space: lowercase letters, digits and dashes, at most 24. Only after the "
            "person has agreed to the name."
        ),
    )
    def create_space(name: str) -> dict:
        c = conn()
        try:
            try:
                created = add_space(c, name)
            except HTTPException as e:
                raise ToolError(str(e.detail)) from e
            return {"name": created, "spaces": list_spaces(c)}
        finally:
            c.close()

    inner = server.streamable_http_app(
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        # Rebinding protection guards servers that trust whoever can reach them. This one trusts
        # nothing but the token, which a rebound page does not have; and the Host it would check
        # is whatever Cloudflare and CapRover pass along.
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    return server, Route("/mcp", endpoint=TokenGuard(inner.routes[0].endpoint, settings.mcp_token))


class TokenGuard:
    """The MCP endpoint behind `Authorization: Bearer <TARTIB_MCP_TOKEN>`, compared in constant
    time. A class, not a function: Starlette hands a plain function a Request, and this has to
    pass the raw ASGI call through to the SDK's transport."""

    def __init__(self, app, token: str | None):
        self.app = app
        self.token = (token or "").encode()

    async def __call__(self, scope, receive, send):
        headers = dict(scope.get("headers") or [])
        given = headers.get(b"authorization", b"")
        ok = (
            bool(self.token)
            and given[:7].lower() == b"bearer "
            and hmac.compare_digest(given[7:].strip(), self.token)
        )
        if not ok:
            response = JSONResponse({"detail": "authentication required"}, status_code=401)
            await response(scope, receive, send)
            return
        # Stateless and JSON-only: nothing is ever pushed, so a GET would only hold a stream open.
        if scope.get("method") == "GET":
            await JSONResponse({"detail": "POST only"}, status_code=405)(scope, receive, send)
            return
        await self.app(scope, receive, send)
