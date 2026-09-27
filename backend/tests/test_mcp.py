"""Tartib over MCP (slice 35), through the SDK's own client against the app on a real port."""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager

import httpx
import httpx2
import pytest
import uvicorn
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from tartib.main import create_app
from tests.conftest import AI_ENV, FAKE_VARS, PASSWORD, make_settings, proposal, set_classify_reply

TOKEN = "mcp-test-token-long-enough-to-be-accepted"
TOOLS = {
    "list_spaces",
    "list_items",
    "search",
    "get_item",
    "add_note",
    "add_task",
    "add_thought",
    "set_status",
    "set_due",
    "set_star",
    "create_space",
    "edit_item",
    "delete_item",
    "edit_thought",
    "delete_thought",  # slice 37
}


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def served(tmp_path, monkeypatch):
    """The app under uvicorn with MCP on and the fake classifier; yields its base URL."""
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    settings = make_settings(tmp_path, **AI_ENV, TARTIB_MCP_TOKEN=TOKEN)
    port = free_port()
    server = uvicorn.Server(
        uvicorn.Config(create_app(settings), host="127.0.0.1", port=port, log_level="warning")
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/api/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield base
    server.should_exit = True
    thread.join(timeout=5)


@asynccontextmanager
async def session(base, token=TOKEN, name="test-agent", url_client=None, user_agent=None):
    headers = {"Authorization": f"Bearer {token}"}
    if user_agent:
        headers["User-Agent"] = user_agent
    url = f"{base}/mcp" + (f"?client={url_client}" if url_client else "")
    async with httpx2.AsyncClient(headers=headers, timeout=10) as http:
        async with streamable_http_client(url, http_client=http) as (read, write):
            async with ClientSession(
                read, write, client_info=types.Implementation(name=name, version="1")
            ) as s:
                await s.initialize()
                yield s


def call(s, tool, **args):
    async def go():
        result = await s.call_tool(tool, args)
        text = "".join(c.text for c in result.content if getattr(c, "text", None))
        return result.is_error, (json.loads(text) if text and not result.is_error else text)

    return go()


def api(base, method, path, **kw):
    return httpx.request(
        method, f"{base}{path}", headers={"Authorization": f"Bearer {PASSWORD}"}, **kw
    )


def test_the_token_is_the_only_way_in(served):
    assert httpx.post(f"{served}/mcp", json={}).status_code == 401
    wrong = {"Authorization": "Bearer nope"}
    assert httpx.post(f"{served}/mcp", json={}, headers=wrong).status_code == 401
    login = {"Authorization": f"Bearer {PASSWORD}"}  # the login password is not the token
    assert httpx.post(f"{served}/mcp", json={}, headers=login).status_code == 401


@pytest.mark.parametrize("token", [None, "short-token"])
def test_off_without_a_token_or_with_a_short_one(tmp_path, token):
    from fastapi.testclient import TestClient

    extra = {"TARTIB_MCP_TOKEN": token} if token else {}
    with TestClient(create_app(make_settings(tmp_path, **extra))) as client:
        r = client.post("/mcp", json={}, headers={"Authorization": f"Bearer {token}"})
        assert r.status_code in (404, 405)


def test_get_holds_nothing_open(served):
    r = httpx.get(f"{served}/mcp", headers={"Authorization": f"Bearer {TOKEN}"}, timeout=5)
    assert r.status_code == 405


def test_the_tools(served):
    async def go():
        async with session(served) as s:
            listed = await s.list_tools()
            names = {t.name for t in listed.tools}
            assert names == TOOLS
            instructions = s.initialize_result.instructions or ""
            assert "list_spaces" in instructions and "asking the person" in instructions
            assert "only when the person asks" in instructions

    asyncio.run(go())


def test_the_namazee_flow(served):
    api(served, "POST", "/api/spaces", json={"name": "namazee"})
    task = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "task", "space": "namazee", "text": "Add prayer times widget"},
    ).json()
    api(served, "POST", "/api/items", json={"shape": "note", "space": "namazee", "text": "Ideas"})

    async def go():
        async with session(served, name="claude-code") as s:
            err, got = await call(s, "list_items", space="namazee")
            assert not err
            assert [i["id"] for i in got["items"]][0] == task["id"]  # open tasks first
            err, done = await call(s, "set_status", id=task["id"], status="done")
            assert not err and done["status"] == "done"
            err, _ = await call(s, "add_thought", id=task["id"], text="Shipped in PR 12.")
            assert not err
            err, item = await call(s, "get_item", id=task["id"])
            assert item["thoughts"][0]["text"] == "Shipped in PR 12."

    asyncio.run(go())


@pytest.mark.parametrize(
    ("url_client", "user_agent", "via"),
    [
        ("claude-code", None, "claude-code"),  # named on the URL: always wins
        (None, "claude-code/2.1.0 (cli)", "claude-code"),  # from the User-Agent
        (None, None, "agent"),  # an HTTP library's User-Agent names nobody
    ],
)
def test_a_note_to_a_named_space_files_directly_and_says_who(served, url_client, user_agent, via):
    async def go():
        async with session(served, url_client=url_client, user_agent=user_agent) as s:
            err, got = await call(s, "add_note", text="Worth sharing: links", space="ideas")
            assert not err and got["filed"] is True
            return got["item"]["id"]

    item_id = asyncio.run(go())
    item = api(served, "GET", f"/api/items/{item_id}").json()
    assert item["stage"] == "filed" and item["space"] == "ideas"
    assert item["via"] == via


def test_a_task_without_a_space_goes_to_the_classifier(served, monkeypatch):
    set_classify_reply(
        monkeypatch, proposal(shape="task", text="call the bank", space="finance", title="Call")
    )

    async def go():
        async with session(served) as s:
            err, got = await call(s, "add_task", text="call the bank")
            assert not err and got["filed"] is False
            return got["capture_id"]

    capture_id = asyncio.run(go())
    for _ in range(100):
        cap = api(served, "GET", f"/api/captures/{capture_id}").json()
        if cap["status"] != "pending":
            break
        time.sleep(0.05)
    assert cap["items"][0]["space"] == "finance"


def test_spaces_unknown_and_new(served):
    async def go():
        async with session(served) as s:
            err, text = await call(s, "add_note", text="x", space="learning-with-ai")
            assert err and "spaces are:" in text
            err, got = await call(s, "create_space", name="learning-with-ai")
            assert not err and "learning-with-ai" in got["spaces"]
            err, got = await call(s, "add_note", text="What we learned", space="learning-with-ai")
            assert not err and got["filed"]
            err, text = await call(s, "set_star", id=got["item"]["id"], starred=True)
            assert err and "note" in text  # star, due and status are for tasks
            err, text = await call(s, "add_task", text="t", space="ideas", due="next week")
            assert err and "YYYY-MM-DD" in text
            err, text = await call(s, "add_note", text="x" * 20_001, space="ideas")
            assert err and "20000" in text

    asyncio.run(go())


def test_an_edit_needs_the_updated_at_it_read(served):
    note = api(
        served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "Draft"}
    ).json()

    async def go():
        async with session(served) as s:
            _, item = await call(s, "get_item", id=note["id"])
            err, text = await call(
                s, "edit_item", id=note["id"], text="Stale", updated_at="2000-01-01T00:00:00Z"
            )
            assert err and "changed since you read it" in text
            err, got = await call(
                s, "edit_item", id=note["id"], text="Final draft", updated_at=item["updated_at"]
            )
            assert not err and got["text"] == "Final draft"
            # The same updated_at a second time is now stale.
            err, _ = await call(
                s, "edit_item", id=note["id"], text="Again", updated_at=item["updated_at"]
            )
            assert err

    asyncio.run(go())
    assert api(served, "GET", f"/api/items/{note['id']}").json()["raw_text"] == "Final draft"


def test_a_task_edit_retitles_it(served):
    task = api(
        served, "POST", "/api/items", json={"shape": "task", "space": "ideas", "text": "Old"}
    ).json()

    async def go():
        async with session(served) as s:
            _, item = await call(s, "get_item", id=task["id"])
            err, got = await call(
                s,
                "edit_item",
                id=task["id"],
                text="New title\n\nbody",
                updated_at=item["updated_at"],
            )
            assert not err and got["title"] == "New title"

    asyncio.run(go())


def test_delete_keeps_the_capture(served):
    note = api(
        served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "Gone"}
    ).json()

    async def go():
        async with session(served) as s:
            err, got = await call(s, "delete_item", id=note["id"])
            assert not err and got["ok"]
            err, text = await call(s, "get_item", id=note["id"])
            assert err and "no item" in text

    asyncio.run(go())
    assert api(served, "GET", f"/api/items/{note['id']}").status_code == 404
    capture = api(served, "GET", f"/api/captures/{note['capture_id']}")
    assert capture.status_code == 200 and capture.json()["raw_text"] == "Gone"


def test_thoughts_are_edited_and_deleted(served):
    one = api(
        served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "One"}
    ).json()
    two = api(
        served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "Two"}
    ).json()

    async def go():
        async with session(served) as s:
            await call(s, "add_thought", id=one["id"], text="first")
            await call(s, "add_thought", id=one["id"], text="second")
            _, item = await call(s, "get_item", id=one["id"])
            first, second = item["thoughts"]
            assert first["edited_at"] is None
            err, got = await call(
                s, "edit_thought", id=one["id"], thought_id=first["id"], text="first, revised"
            )
            assert not err and got["text"] == "first, revised" and got["edited_at"]
            err, text = await call(
                s, "edit_thought", id=two["id"], thought_id=first["id"], text="x"
            )
            assert err and "has no thought" in text  # a thought only through its own item
            err, got = await call(s, "delete_thought", id=one["id"], thought_id=second["id"])
            assert not err and got["thought_count"] == 1
            _, item = await call(s, "get_item", id=one["id"])
            assert [t["text"] for t in item["thoughts"]] == ["first, revised"]

    asyncio.run(go())
