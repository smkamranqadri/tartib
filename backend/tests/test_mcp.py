"""Tartib over MCP (slice 35), through the SDK's own client against the app on a real port."""

from __future__ import annotations

import asyncio
import json
import re
import socket
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import httpx2
import pytest
import uvicorn
from mcp import ClientSession, types
from mcp.client.streamable_http import streamable_http_client

from tartib import db
from tartib.main import create_app
from tests.conftest import AI_ENV, FAKE_VARS, PASSWORD, make_settings, proposal, set_classify_reply

TOKEN = "mcp-test-token-long-enough-to-be-accepted"
TOOLS = {
    "list_spaces",
    "set_space_description",
    "list_items",
    "search",
    "get_item",
    "add_note",
    "add_task",
    "add_thought",
    "set_status",
    "set_due",
    "set_star",
    "set_reminder",
    "create_space",
    "edit_item",
    "find_replace",
    "delete_item",
    "edit_thought",
    "delete_thought",  # slice 37
    "start_session",
    "get_session",
    "end_session",
    "reminders_due",  # slice 39
    "today",  # slice 41
    "pick",
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
            assert len(listed.tools) == len(TOOLS) == 24
            pick = next(t for t in listed.tools if t.name == "pick")
            assert "about 9 seconds" in pick.description and "17.6" in pick.description
            instructions = s.initialize_result.instructions or ""
            assert "list_spaces" in instructions and "asking the person" in instructions
            assert "only when the person asks" in instructions
            assert "find_replace" in instructions and "Read its description" in instructions
            assert "- today lists" in instructions and "- pick stars" in instructions

    asyncio.run(go())


def test_space_description_details_writes_and_validation(served):
    async def go():
        async with session(served) as s:
            err, spaces = await call(s, "list_spaces")
            assert not err and spaces["spaces"] == [
                "work",
                "home",
                "health",
                "finance",
                "ideas",
                "travel",
            ]
            detail = next(d for d in spaces["details"] if d["name"] == "work")
            assert detail["description"] == "" and detail["updated_at"] == ""
            err, saved = await call(
                s,
                "set_space_description",
                space="work",
                description="School\r\nfollow-ups",
                updated_at="",
            )
            assert not err and saved["description"] == "School\nfollow-ups"
            err, again = await call(
                s,
                "set_space_description",
                space="work",
                description=saved["description"],
                updated_at=saved["updated_at"],
            )
            assert not err and again["updated_at"] > saved["updated_at"]
            err, stale = await call(
                s,
                "set_space_description",
                space="work",
                description="lost",
                updated_at=saved["updated_at"],
            )
            assert err and "changed elsewhere" in stale
            err, too_long = await call(
                s,
                "set_space_description",
                space="work",
                description="x" * 501,
                updated_at=again["updated_at"],
            )
            assert err and "500 characters" in too_long
            err, controls = await call(
                s,
                "set_space_description",
                space="work",
                description="x\ty",
                updated_at=again["updated_at"],
            )
            assert err and "control character" in controls
            err, listed = await call(s, "list_items", space="work")
            assert not err and listed["description"] == "School\nfollow-ups"

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


def test_a_reminder_is_set_in_the_owners_zone_and_rearms(served):
    task = api(
        served, "POST", "/api/items", json={"shape": "task", "space": "ideas", "text": "Call"}
    ).json()
    note = api(
        served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "N"}
    ).json()

    async def go():
        async with session(served) as s:
            # No offset: read in TARTIB_TZ (Asia/Karachi, +05:00), stored in UTC.
            err, got = await call(s, "set_reminder", id=task["id"], remind_at="2099-01-02T18:00")
            assert not err and got["remind_at"] == "2099-01-02T13:00:00Z"
            err, got = await call(
                s, "set_reminder", id=task["id"], remind_at="2099-01-02T18:00:00+00:00"
            )
            assert not err and got["remind_at"] == "2099-01-02T18:00:00Z"
            err, text = await call(s, "set_reminder", id=task["id"], remind_at="2020-01-01T09:00")
            assert err and "passed" in text and "Asia/Karachi" in text
            err, text = await call(s, "set_reminder", id=task["id"], remind_at="at six")
            assert err and "ISO 8601" in text
            err, text = await call(s, "set_reminder", id=note["id"], remind_at="2099-01-02T18:00")
            assert err and "note" in text
            err, got = await call(s, "set_reminder", id=task["id"])
            assert not err and got["remind_at"] is None

    asyncio.run(go())


def test_a_moved_reminder_fires_again(served, tmp_path):
    task = api(
        served, "POST", "/api/items", json={"shape": "task", "space": "ideas", "text": "Call"}
    ).json()
    api(served, "PATCH", f"/api/items/{task['id']}", json={"remind_at": "2099-01-01T00:00:00Z"})
    c = db.connect(tmp_path / "t.db")
    c.execute("UPDATE items SET reminded_at = '2099-01-01T00:00:00Z' WHERE id = ?", (task["id"],))
    c.commit()

    async def go():
        async with session(served) as s:
            err, _ = await call(s, "set_reminder", id=task["id"], remind_at="2099-01-03T09:00")
            assert not err

    asyncio.run(go())
    row = c.execute("SELECT reminded_at FROM items WHERE id = ?", (task["id"],)).fetchone()
    assert row["reminded_at"] is None  # the same update path as the app: moving it re-arms it
    c.close()


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


def test_find_replace_updates_item_and_thoughts(served):
    task = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "task", "space": "ideas", "text": "Draft title\nDraft in body"},
    ).json()
    source = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "note", "space": "ideas", "text": "See [[Draft title]]"},
    ).json()

    async def go():
        async with session(served) as s:
            err, _ = await call(s, "add_thought", id=task["id"], text="Draft thought Draft")
            assert not err
            _, item = await call(s, "get_item", id=task["id"])
            err, got = await call(
                s,
                "find_replace",
                id=task["id"],
                find="Draft",
                replace="Revised",
                updated_at=item["updated_at"],
            )
            assert not err
            assert set(got) == {"id", "updated_at", "replacements", "changed_lines"}
            _, revised = await call(s, "get_item", id=task["id"])
            assert revised["text"] == "Revised title\nRevised in body"
            assert revised["title"] == "Revised title"
            assert got["updated_at"] == revised["updated_at"]
            assert got["replacements"] == {"item_text": 2, "thoughts": 2}
            assert revised["thoughts"][0]["text"] == "Revised thought Revised"
            assert revised["thoughts"][0]["edited_at"]
            assert len(got["changed_lines"]) == 2

            err, found = await call(s, "search", query="Revised thought")
            assert not err and any(i["id"] == task["id"] for i in found["items"])
            err, found = await call(s, "search", query="Draft")
            assert not err and not any(i["id"] == task["id"] for i in found["items"])

    asyncio.run(go())
    assert api(served, "GET", f"/api/items/{source['id']}").json()["raw_text"] == (
        "See [[Revised title]]"
    )


def test_find_replace_no_match_is_a_noop_and_stale_read_is_refused(served):
    note = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "note", "space": "ideas", "text": "Keep this text"},
    ).json()

    async def go():
        async with session(served) as s:
            err, _ = await call(s, "add_thought", id=note["id"], text="Needle")
            assert not err
            _, item = await call(s, "get_item", id=note["id"])
            err, got = await call(
                s,
                "find_replace",
                id=note["id"],
                find="keep",
                replace="present",
                updated_at=item["updated_at"],
            )
            assert not err
            assert got["changed_lines"] == []
            assert got["updated_at"] == item["updated_at"]
            assert got["replacements"] == {"item_text": 0, "thoughts": 0}

            err, message = await call(
                s,
                "find_replace",
                id=note["id"],
                find="",
                replace="present",
                updated_at=item["updated_at"],
            )
            assert err and "find text is empty" in message

            err, message = await call(
                s,
                "find_replace",
                id=note["id"],
                find="Needle",
                replace="",
                updated_at=item["updated_at"],
            )
            assert err and "thought" in message and "no changes were made" in message

            err, message = await call(
                s,
                "find_replace",
                id=note["id"],
                find="Keep this text",
                replace="",
                updated_at=item["updated_at"],
            )
            assert err and "item's text empty" in message

            _, unchanged = await call(s, "get_item", id=note["id"])
            assert unchanged["text"] == "Keep this text"
            assert unchanged["thoughts"][0]["text"] == "Needle"

            err, message = await call(
                s,
                "find_replace",
                id=note["id"],
                find="Keep",
                replace="Change",
                updated_at="2000-01-01T00:00:00Z",
            )
            assert err and "changed since you read it" in message

    asyncio.run(go())
    assert api(served, "GET", f"/api/items/{note['id']}").json()["raw_text"] == "Keep this text"


def test_find_replace_expected_scope_and_compact_response(served):
    text = "Header\n" + "Unchanged content\n" * 600 + "\n".join(
        f"Rule {i} (×4)" for i in range(7)
    )
    note = api(served, "POST", "/api/items", json={
        "shape": "note", "space": "ideas", "text": text,
    }).json()

    async def go():
        async with session(served) as s:
            await call(s, "add_thought", id=note["id"], text="Rule 0 (×4)")
            _, original = await call(s, "get_item", id=note["id"])
            thought = original["thoughts"][0]
            args = dict(id=note["id"], find="(×4)", replace="(×5)",
                        updated_at=original["updated_at"])
            for expected, scope, count in [(1, "text", 7), (7, "both", 8), (0, "thoughts", 1)]:
                err, message = await call(s, "find_replace", **args, expected=expected, scope=scope)
                assert err and f"found {count}" in message and "no changes" in message
                _, unchanged = await call(s, "get_item", id=note["id"])
                assert unchanged == original
            err, message = await call(s, "find_replace", **args, expected=-1)
            assert err and "non-negative" in message
            err, _ = await call(s, "find_replace", **args, scope="invalid")
            assert err
            err, got = await call(s, "find_replace", id=note["id"], find="Rule 0 (×4)",
                                 replace="Rule 0 (×5)", updated_at=original["updated_at"],
                                 expected=1, scope="text")
            assert not err
            assert set(got) == {"id", "updated_at", "replacements", "changed_lines"}
            assert got["replacements"] == {"item_text": 1, "thoughts": 0}
            assert got["changed_lines"] == [{"scope": "text", "lines": [{
                "before_line": 602, "after_line": 602,
                "before": ["Rule 0 (×4)\n"], "after": ["Rule 0 (×5)\n"],
            }]}]
            assert len(json.dumps(got)) < 500
            _, current = await call(s, "get_item", id=note["id"])
            assert current["text"] == text.replace("Rule 0 (×4)", "Rule 0 (×5)")
            assert current["thoughts"] == original["thoughts"]
            assert current["updated_at"] == got["updated_at"]
            assert got["updated_at"] != original["updated_at"]
            # Thought edits leave the parent timestamp unchanged; use the current body.
            err, _ = await call(s, "edit_thought", id=note["id"], thought_id=thought["id"],
                                text="Rule 0 (×4)\nConcurrent content")
            assert not err
            err, got = await call(s, "find_replace", id=note["id"], find="(×4)", replace="(×5)",
                                 updated_at=current["updated_at"], expected=1, scope="thoughts")
            assert not err and got["replacements"] == {"item_text": 0, "thoughts": 1}
            assert got["updated_at"] == current["updated_at"]
            assert got["changed_lines"][0]["thought_id"] == thought["id"]
            assert "Concurrent content" not in json.dumps(got)
            _, final = await call(s, "get_item", id=note["id"])
            assert final["text"] == current["text"]
            assert final["thoughts"][0]["text"] == "Rule 0 (×5)\nConcurrent content"
            err, noop = await call(s, "find_replace", id=note["id"], find="absent", replace="x",
                                  updated_at=final["updated_at"], expected=0)
            assert not err and noop["changed_lines"] == []
            _, unchanged = await call(s, "get_item", id=note["id"])
            assert unchanged == final

    asyncio.run(go())


def test_find_replace_preserves_whitespace_and_reports_multiline_changes(served):
    note = api(served, "POST", "/api/items", json={
        "shape": "note", "space": "ideas", "text": "Needle",
    }).json()

    async def go():
        async with session(served) as s:
            await call(s, "add_thought", id=note["id"], text="Needle")
            _, item = await call(s, "get_item", id=note["id"])
            err, _ = await call(s, "find_replace", id=note["id"], find="Needle",
                                replace="  Needle\nkept\n  ",
                                updated_at=item["updated_at"], expected=2)
            assert not err
            _, item = await call(s, "get_item", id=note["id"])
            assert item["text"] == item["thoughts"][0]["text"] == "  Needle\nkept\n  "
            err, got = await call(s, "find_replace", id=note["id"], find="Needle",
                                 replace="First\nSecond", updated_at=item["updated_at"], expected=2)
            assert not err
            _, item = await call(s, "get_item", id=note["id"])
            assert item["text"] == item["thoughts"][0]["text"] == "  First\nSecond\nkept\n  "
            for change in got["changed_lines"]:
                assert change["lines"] == [{"before_line": 1, "after_line": 1,
                    "before": ["  Needle\n"], "after": ["  First\n", "Second\n"]}]
            err, noop = await call(s, "find_replace", id=note["id"], find="First", replace="First",
                                  updated_at=item["updated_at"], expected=2)
            assert not err and noop["changed_lines"] == []
            _, unchanged = await call(s, "get_item", id=note["id"])
            assert unchanged == item

    asyncio.run(go())


def test_find_replace_respects_text_limits_without_partial_changes(served):
    long_text = "a" * 11_000
    note = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "note", "space": "ideas", "text": long_text},
    ).json()
    thought_note = api(
        served,
        "POST",
        "/api/items",
        json={"shape": "note", "space": "ideas", "text": "safe"},
    ).json()

    async def go():
        async with session(served) as s:
            _, item = await call(s, "get_item", id=note["id"])
            err, message = await call(
                s,
                "find_replace",
                id=note["id"],
                find="a",
                replace="aa",
                updated_at=item["updated_at"],
            )
            assert err and "item's text over 20000 characters" in message
            _, unchanged = await call(s, "get_item", id=note["id"])
            assert unchanged["text"] == long_text

            err, _ = await call(s, "add_thought", id=thought_note["id"], text=long_text)
            assert not err
            _, item = await call(s, "get_item", id=thought_note["id"])
            err, message = await call(
                s,
                "find_replace",
                id=thought_note["id"],
                find="a",
                replace="aa",
                updated_at=item["updated_at"],
            )
            assert err and "thought" in message and "over 20000 characters" in message
            _, unchanged = await call(s, "get_item", id=thought_note["id"])
            assert unchanged["text"] == "safe"
            assert unchanged["thoughts"][0]["text"] == long_text

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


def test_search_and_list_items_return_summaries_not_whole_items(served):
    """A search or a list over long items is what blew agents' context up: each hit is a short
    summary (first line and a snippet), and get_item stays the way to read one in full."""
    body = "Preamble about context budgets.\n" + "A context line with the marker needle.\n" * 300
    notes = [
        api(served, "POST", "/api/items", json={
            "shape": "note", "space": "ideas", "text": f"{body}\ncopy {n}",
        }).json()
        for n in range(3)
    ]
    assert all(len(n["raw_text"]) > 10_000 for n in notes)  # ~30k chars if returned whole

    async def go():
        async with session(served) as s:
            err, found = await call(s, "search", query="needle")
            assert not err
            assert {i["id"] for i in found["items"]} == {n["id"] for n in notes}
            err, listed = await call(s, "list_items", space="ideas")
            assert not err
            assert {i["id"] for i in listed["items"]} == {n["id"] for n in notes}
            for result in (found, listed):
                for hit in result["items"]:
                    assert "text" not in hit
                    assert hit["first_line"] == "Preamble about context budgets."
                    assert "needle" in hit["snippet"]
            # The whole reply is a summary, not ~30k chars of body.
            assert len(json.dumps(found)) < 2_000
            assert len(json.dumps(listed)) < 2_000
            # get_item is unchanged: the whole item, thoughts and links.
            _, whole = await call(s, "get_item", id=notes[0]["id"])
            assert whole["text"] == notes[0]["raw_text"] and len(whole["text"]) > 10_000

    asyncio.run(go())


def test_a_hit_found_through_a_thought_shows_the_thought(served):
    """A search matches thoughts too; its hit's snippet comes from the matched thought, so the
    agent can see why an item whose own text lacks the word came back."""
    note = api(served, "POST", "/api/items", json={
        "shape": "note", "space": "ideas", "text": "A note with nothing special in its own text.",
    }).json()

    async def go():
        async with session(served) as s:
            await call(s, "add_thought", id=note["id"], text="The zebra crossing is where it goes.")
            err, found = await call(s, "search", query="zebra")
            assert not err
            hit = next(i for i in found["items"] if i["id"] == note["id"])
            assert "text" not in hit
            assert "zebra" in hit["snippet"]

    asyncio.run(go())


# --- slice 39: sessions and reminders_due ---


def make_task(base, text="Call", space="ideas") -> dict:
    body = {"shape": "task", "space": space, "text": text}
    return api(base, "POST", "/api/items", json=body).json()


def set_cols(tmp_path, item_id: int, **cols) -> None:
    c = db.connect(tmp_path / "t.db")
    sets = ", ".join(f"{k} = ?" for k in cols)
    c.execute(f"UPDATE items SET {sets} WHERE id = ?", (*cols.values(), item_id))
    c.commit()
    c.close()


def moment(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_the_session_tools_carry_the_server_clock(served):
    async def go():
        async with session(served) as s:
            err, got = await call(s, "get_session")
            assert not err and got["state"] is None and got["session"] is None
            assert got["remaining_seconds"] is None and got["server_time"].endswith("Z")

            err, started = await call(s, "start_session")
            assert not err and started["state"] == "running"
            assert 1490 <= started["remaining_seconds"] <= 1500
            assert moment(started["session"]["ends_at"]) - moment(started["server_time"]) == (
                timedelta(seconds=started["remaining_seconds"])
            )
            assert started["session"]["item_id"] is None and started["item"] is None

            err, text = await call(s, "start_session")
            assert err and "already running" in text
            err, text = await call(s, "start_session", item_id=99999)
            assert err and "already running" in text  # one at a time is checked first

            err, got = await call(s, "get_session")
            assert got["state"] == "running" and got["session"]["id"] == started["session"]["id"]

            # Stopped without an outcome: it is owed one, and it ended now, not at ends_at.
            err, ended = await call(s, "end_session")
            assert not err and ended["state"] == "awaiting"
            stopped = ended["session"]
            assert stopped["outcome"] is None and stopped["ended_at"] < stopped["ends_at"]
            assert moment(ended["server_time"]) - moment(stopped["ended_at"]) < timedelta(seconds=5)
            assert ended["remaining_seconds"] is None

            err, got = await call(s, "get_session")
            assert got["state"] == "awaiting" and got["remaining_seconds"] is None

            err, text = await call(s, "end_session")
            assert err and "pass an outcome" in text

            err, done = await call(s, "end_session", outcome="unfinished")
            assert not err and done["state"] is None and done["session"]["outcome"] == "unfinished"

            err, got = await call(s, "get_session")
            assert got["state"] is None
            # a second outcome has nothing to land on
            err, text = await call(s, "end_session", outcome="done")
            assert err and "no session is running" in text

    asyncio.run(go())


def test_an_unknown_task_is_refused_when_nothing_is_running(served):
    async def go():
        async with session(served) as s:
            err, text = await call(s, "start_session", item_id=99999)
            assert err and "item not found" in text
            err, got = await call(s, "get_session")
            assert got["state"] is None  # the refusal left no row behind

    asyncio.run(go())


def test_an_outcome_done_ticks_the_task_and_the_others_do_not(served):
    one, two, three = (make_task(served, t) for t in ("One", "Two", "Three"))

    def status(task):
        return api(served, "GET", f"/api/items/{task['id']}").json()["status"]

    async def go():
        async with session(served) as s:
            err, got = await call(s, "start_session", item_id=one["id"])
            assert not err and got["item"]["id"] == one["id"]
            err, got = await call(s, "end_session", outcome="done")  # stop and answer in one call
            assert not err and got["session"]["outcome"] == "done"
            assert status(one) == "done"
            # it ended now: an outcome on a still-running row would stamp ends_at, 25 minutes on
            assert got["session"]["ended_at"] <= got["server_time"] < got["session"]["ends_at"]

            await call(s, "start_session", item_id=two["id"])
            err, got = await call(s, "end_session", outcome="unfinished")
            assert not err and status(two) == "open"

            await call(s, "start_session", item_id=three["id"])
            await call(s, "end_session")
            err, got = await call(s, "end_session", outcome="abandoned")  # answers the waiting one
            assert not err and got["session"]["outcome"] == "abandoned" and status(three) == "open"

            err, text = await call(s, "end_session", outcome="finished")
            assert err  # not one of the three words

    asyncio.run(go())


@pytest.fixture
def served_app(tmp_path, monkeypatch):
    """Like `served`, with push on and the app handed back, to reach the session timers."""
    from tests.test_reminders import QUIET, VAPID

    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    settings = make_settings(tmp_path, **{**AI_ENV, **VAPID, **QUIET}, TARTIB_MCP_TOKEN=TOKEN)
    app = create_app(settings)
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/api/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    yield base, app
    server.should_exit = True
    thread.join(timeout=5)


def wait_for(check) -> None:
    for _ in range(100):
        if check():
            return
        time.sleep(0.05)
    raise AssertionError("timed out")


def test_a_started_session_pushes_once_and_an_early_end_calls_it_off(served_app):
    from tests.test_reminders import FakeSender

    base, app = served_app
    clock, sender = app.state.sessions, FakeSender()
    clock._sender = sender
    api(
        base, "POST", "/api/subscriptions",
        json={"endpoint": "https://push.example/a", "keys": {"p256dh": "k", "auth": "a"}},
    )

    async def go():
        async with session(base) as s:
            err, ran = await call(s, "start_session")
            sid = ran["session"]["id"]
            wait_for(lambda: sid in clock._timers)  # armed, as the app's own start arms it
            # the timer would fire at ends_at; do that now, on the injected clock
            ends = moment(ran["session"]["ends_at"])
            assert clock.fire(sid, now=ends) is True
            assert clock.fire(sid, now=ends) is False  # once
            assert [p["tag"] for _, p in sender.sent] == [f"session-{sid}"]

            await call(s, "end_session", outcome="abandoned")
            err, early = await call(s, "start_session")
            sid2 = early["session"]["id"]
            wait_for(lambda: sid2 in clock._timers)
            await call(s, "end_session")
            wait_for(lambda: sid2 not in clock._timers)  # disarmed
            assert clock.fire(sid2, now=moment(early["session"]["ends_at"])) is False
            assert len(sender.sent) == 1

    asyncio.run(go())


def due_ids(got):
    return [i["id"] for i in got["items"]]


def test_reminders_due_lists_open_tasks_across_spaces_pushed_ones_included(served, tmp_path):
    early = make_task(served, "Early", "ideas")
    pushed = make_task(served, "Pushed", "work")
    late = make_task(served, "Late", "ideas")
    set_cols(tmp_path, early["id"], remind_at="2026-01-01T09:00:00Z")
    set_cols(
        tmp_path, pushed["id"], remind_at="2026-01-02T09:00:00Z", reminded_at="2026-01-02T09:00:05Z"
    )
    set_cols(tmp_path, late["id"], remind_at="2026-01-03T09:00:00Z")

    async def go():
        async with session(served) as s:
            err, got = await call(s, "reminders_due", until="2026-01-02T09:00:00Z")
            assert not err
            assert due_ids(got) == [early["id"], pushed["id"]]  # oldest first, until inclusive
            by_id = {i["id"]: i for i in got["items"]}
            assert by_id[pushed["id"]]["reminded_at"] == "2026-01-02T09:00:05Z"
            assert by_id[early["id"]]["reminded_at"] is None
            assert {by_id[early["id"]]["space"], by_id[pushed["id"]]["space"]} == {"ideas", "work"}
            assert by_id[early["id"]]["remind_at"] == "2026-01-01T09:00:00Z"
            assert by_id[early["id"]]["first_line"] == "Early"
            assert got["truncated"] is False and got["since"] is None
            assert got["until"] == "2026-01-02T09:00:00Z" and got["server_time"].endswith("Z")

    asyncio.run(go())


def test_reminders_due_leaves_out_what_is_not_an_open_filed_reminder(served, tmp_path):
    kept = make_task(served, "Kept")
    done = make_task(served, "Done")
    bare = make_task(served, "No reminder")
    note = api(served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "N"})
    waiting = make_task(served, "Waiting")
    for task in (kept, done, waiting):
        set_cols(tmp_path, task["id"], remind_at="2026-01-01T09:00:00Z")
    set_cols(tmp_path, waiting["id"], stage="attention")  # not filed yet

    async def go():
        async with session(served) as s:
            await call(s, "set_status", id=done["id"], status="done")
            err, got = await call(s, "reminders_due", until="2030-01-01T00:00:00Z")
            assert not err and due_ids(got) == [kept["id"]]
            assert bare["id"] not in due_ids(got) and note.json()["id"] not in due_ids(got)

    asyncio.run(go())


def test_reminders_due_since_is_exclusive_and_a_poll_repeats_nothing(served, tmp_path):
    a, b, c = (make_task(served, t) for t in ("A", "B", "C"))
    for task, at in ((a, "09:00"), (b, "10:00"), (c, "11:00")):
        set_cols(tmp_path, task["id"], remind_at=f"2026-01-01T{at}:00Z")

    async def go():
        async with session(served) as s:
            err, first = await call(s, "reminders_due", until="2026-01-01T10:00:00Z")
            assert due_ids(first) == [a["id"], b["id"]]
            err, second = await call(
                s, "reminders_due", until="2026-01-01T11:00:00Z", since=first["until"]
            )
            assert not err and due_ids(second) == [c["id"]]  # b sits exactly on `since`
            assert second["since"] == "2026-01-01T10:00:00Z"
            err, third = await call(
                s, "reminders_due", until="2026-01-01T11:00:00Z", since=second["until"]
            )
            assert not err and third["items"] == []

    asyncio.run(go())


def test_reminders_due_shows_a_moved_reminder_as_it_is_stored(served, tmp_path):
    task = make_task(served)

    async def go():
        async with session(served) as s:
            err, _ = await call(s, "set_reminder", id=task["id"], remind_at="2099-01-02T18:00")
            err, got = await call(s, "reminders_due", until="2099-12-31T00:00:00Z")
            assert due_ids(got) == [task["id"]]
            assert got["items"][0]["remind_at"] == "2099-01-02T13:00:00Z"  # as stored, in UTC
            err, _ = await call(s, "set_reminder", id=task["id"], remind_at="2099-01-03T09:00")
            err, got = await call(s, "reminders_due", until="2099-12-31T00:00:00Z")
            assert got["items"][0]["remind_at"] == "2099-01-03T04:00:00Z"

    asyncio.run(go())


def test_reminders_due_caps_at_the_oldest_hundred(served, tmp_path):
    ids = []
    for n in range(101):
        task = make_task(served, f"T{n}")
        set_cols(tmp_path, task["id"], remind_at=f"2026-01-01T{n // 60:02d}:{n % 60:02d}:00Z")
        ids.append(task["id"])

    async def go():
        async with session(served) as s:
            err, got = await call(s, "reminders_due", until="2026-12-31T00:00:00Z")
            assert not err and got["truncated"] is True and due_ids(got) == ids[:100]
            err, got = await call(s, "reminders_due", until="2026-01-01T01:39:00Z")
            assert got["truncated"] is False and len(got["items"]) == 100

    asyncio.run(go())


def test_reminders_due_reads_times_in_the_owners_zone_and_refuses_bad_ones(served, tmp_path):
    task = make_task(served)
    set_cols(tmp_path, task["id"], remind_at="2026-01-01T13:00:00Z")  # 18:00 in Karachi

    async def go():
        async with session(served) as s:
            err, got = await call(s, "reminders_due", until="2026-01-01T18:00")  # Asia/Karachi
            assert not err and due_ids(got) == [task["id"]]
            assert got["until"] == "2026-01-01T13:00:00Z"
            err, got = await call(s, "reminders_due", until="2026-01-01T17:59")
            assert not err and got["items"] == []
            err, text = await call(
                s, "reminders_due", until="2026-01-01T00:00:00Z", since="2026-01-02T00:00:00Z"
            )
            assert err and "before since" in text
            err, text = await call(s, "reminders_due", until="tomorrow")
            assert err and "ISO 8601" in text
            err, text = await call(
                s, "reminders_due", until="2026-01-01T00:00:00Z", since="yesterday"
            )
            assert err and "since" in text and "ISO 8601" in text

    asyncio.run(go())


def test_reminders_due_writes_nothing(served, tmp_path):
    task = make_task(served)
    set_cols(
        tmp_path, task["id"], remind_at="2026-01-01T09:00:00Z", reminded_at="2026-01-01T09:00:03Z"
    )

    def snapshot():
        c = db.connect(tmp_path / "t.db")
        row = c.execute("SELECT * FROM items WHERE id = ?", (task["id"],)).fetchone()
        c.close()
        return dict(row)

    before = snapshot()

    async def go():
        async with session(served) as s:
            err, got = await call(s, "reminders_due", until="2030-01-01T00:00:00Z")
            assert not err and due_ids(got) == [task["id"]]

    asyncio.run(go())
    assert snapshot() == before


# --- slice 41: today ---

KARACHI = ZoneInfo("Asia/Karachi")  # AI_ENV's TARTIB_TZ
UTC_STAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
PLAIN_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
PAST = "2026-01-01T09:00:00Z"
TODAY_FIELDS = {"id", "space", "first_line", "due", "starred", "remind_at"}


def day(n: int = 0) -> str:
    """A calendar date n days from today in the app's zone."""
    return (datetime.now(KARACHI).date() + timedelta(days=n)).isoformat()


def today_ids(got):
    return [i["id"] for i in got["items"]]


def test_today_is_in_the_apps_order_and_agrees_with_api_today(served, tmp_path):
    """Made in the reverse of the expected order, so only the sort can produce it."""
    no_due = make_task(served, "No due date, reminder passed")
    later = make_task(served, "Due later, reminder passed")
    due_today = make_task(served, "Due today")
    overdue = make_task(served, "Overdue")
    starred = make_task(served, "Starred and old")
    set_cols(tmp_path, no_due["id"], remind_at=PAST)
    set_cols(tmp_path, later["id"], due=day(4), remind_at=PAST)
    set_cols(tmp_path, due_today["id"], due=day(0))
    set_cols(tmp_path, overdue["id"], due=day(-2))
    set_cols(tmp_path, starred["id"], starred=1, due=day(-5))
    expected = [starred["id"], overdue["id"], due_today["id"], later["id"], no_due["id"]]

    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err
            assert today_ids(got) == expected
            assert got["truncated"] is False

    asyncio.run(go())
    rest = api(served, "GET", "/api/today").json()
    assert [i["id"] for i in rest["items"]] == expected  # the app and the tool share one order


def test_today_leaves_out_notes_done_tasks_and_unfiled_ones(served, tmp_path):
    kept = make_task(served, "Kept")
    done = make_task(served, "Done")
    waiting = make_task(served, "Waiting for a decision")
    not_due = make_task(served, "Not on Today")
    note = api(served, "POST", "/api/items", json={"shape": "note", "space": "ideas", "text": "N"})
    set_cols(tmp_path, kept["id"], due=day(-1))
    set_cols(tmp_path, done["id"], due=day(-1), status="done")
    set_cols(tmp_path, waiting["id"], due=day(-1), stage="attention")
    set_cols(tmp_path, note.json()["id"], starred=1)  # even starred, a note is not a task

    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err and today_ids(got) == [kept["id"]]
            assert not_due["id"] not in today_ids(got)

    asyncio.run(go())


def test_today_includes_a_task_worked_on_in_a_session_today(served):
    worked = make_task(served, "Worked on, otherwise nowhere near Today")

    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err and got["items"] == []
            await call(s, "start_session", item_id=worked["id"])
            await call(s, "end_session")
            err, got = await call(s, "today")
            assert not err and got["items"] == [
                {
                    "id": worked["id"],
                    "space": "ideas",
                    "first_line": "Worked on, otherwise nowhere near Today",
                    "due": None,
                    "starred": False,
                    "remind_at": None,
                }
            ]

    asyncio.run(go())


def test_an_empty_today_is_an_empty_list_not_an_error(served):
    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err
            assert got["items"] == [] and got["truncated"] is False
            assert UTC_STAMP.match(got["server_time"])
            assert set(got) == {"server_time", "items", "truncated"}

    asyncio.run(go())


def test_today_returns_twenty_and_says_when_there_were_more(served, tmp_path):
    """The cut comes after the sort: the 21st task is made last but sorts first, and the task
    dropped is the one that sorts last."""
    ids = []
    for n in range(20):
        task = make_task(served, f"T{n}")
        set_cols(tmp_path, task["id"], starred=1, due=day(n))
        ids.append(task["id"])

    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err and today_ids(got) == ids and got["truncated"] is False

            extra = make_task(served, "The 21st")
            set_cols(tmp_path, extra["id"], starred=1)  # starred with no due date sorts first
            err, got = await call(s, "today")
            assert not err and got["truncated"] is True
            assert today_ids(got) == [extra["id"], *ids[:19]]
            assert ids[19] not in today_ids(got)
            # the app's own Today still lists every row
            assert len(api(served, "GET", "/api/today").json()["items"]) == 21

    asyncio.run(go())


def test_today_items_have_exactly_these_fields_in_these_formats(served, tmp_path):
    full = make_task(served, "x" * 200 + "\nsecond line")
    plain = make_task(served, "Line one\nLine two")
    set_cols(tmp_path, full["id"], starred=1, due=day(3), remind_at="2099-01-02T13:00:00Z")
    set_cols(tmp_path, plain["id"], due=day(-1))

    async def go():
        async with session(served) as s:
            err, got = await call(s, "today")
            assert not err
            assert set(got) == {"server_time", "items", "truncated"}
            assert UTC_STAMP.match(got["server_time"])
            by_id = {i["id"]: i for i in got["items"]}
            assert set(by_id) == {full["id"], plain["id"]}
            for item in got["items"]:
                assert set(item) == TODAY_FIELDS
                assert type(item["id"]) is int and type(item["starred"]) is bool
                assert item["space"] == "ideas"
                assert len(item["first_line"]) <= 120
            a, b = by_id[full["id"]], by_id[plain["id"]]
            assert a["first_line"] == "x" * 120 and a["starred"] is True
            assert PLAIN_DATE.match(a["due"]) and a["due"] == day(3)
            assert UTC_STAMP.match(a["remind_at"]) and a["remind_at"] == "2099-01-02T13:00:00Z"
            assert b["first_line"] == "Line one" and b["starred"] is False
            assert b["due"] == day(-1) and b["remind_at"] is None

    asyncio.run(go())


WRITE_PREFIXES = (
    "INSERT", "UPDATE", "DELETE", "REPLACE", "CREATE", "DROP", "ALTER", "VACUUM", "BEGIN", "COMMIT",
)


def dump_tables(path) -> dict:
    """Every row of every table, the FTS shadow tables included (rows sorted, since a table
    without a rowid has no natural order)."""
    c = sqlite3.connect(path)
    try:
        names = [
            r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " ORDER BY name"
            )
        ]
        return {
            n: sorted((tuple(r) for r in c.execute(f'SELECT * FROM "{n}"')), key=repr)
            for n in names
        }
    finally:
        c.close()


@pytest.fixture
def served_quiet(tmp_path, monkeypatch):
    """`served`, with the app handed back and the two things that write on their own proved
    inert: no push keys means no reminder loop, and a session timer exists only for a session
    started while the app runs, so a session seeded afterwards has none."""
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    app = create_app(make_settings(tmp_path, **AI_ENV, TARTIB_MCP_TOKEN=TOKEN))
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(f"{base}/api/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.05)
    assert app.state.reminders is None and app.state.sessions._timers == {}
    yield base, app
    server.should_exit = True
    thread.join(timeout=5)


def test_today_writes_nothing(served_quiet, tmp_path, monkeypatch):
    """Every statement on every connection is traced, and every table is compared before and
    after. What a stray write would touch is seeded: an unreminded item whose reminder has
    passed, and a session that expired unclosed."""
    base, app = served_quiet
    now = datetime.now(UTC).replace(microsecond=0)
    stamp = lambda moment: moment.isoformat().replace("+00:00", "Z")  # noqa: E731
    unreminded = make_task(base, "Reminder passed, never pushed")
    set_cols(tmp_path, unreminded["id"], due=day(-1), remind_at=stamp(now - timedelta(hours=1)))
    c = db.connect(tmp_path / "t.db")
    c.execute(
        "INSERT INTO sessions (item_id, started_at, ends_at, created_at) VALUES (?, ?, ?, ?)",
        (unreminded["id"], stamp(now - timedelta(minutes=6)), stamp(now - timedelta(minutes=1)),
         stamp(now)),
    )
    c.commit()
    c.close()
    assert app.state.sessions._timers == {}

    trace: list[str] = []
    real_connect = db.connect

    def traced(path):
        conn = real_connect(path)
        conn.set_trace_callback(trace.append)
        return conn

    monkeypatch.setattr(db, "connect", traced)

    def writes():
        return [s for s in trace if s.lstrip().upper().startswith(WRITE_PREFIXES)]

    watcher = sqlite3.connect(tmp_path / "t.db")  # data_version moves when another one commits
    version = lambda: watcher.execute("PRAGMA data_version").fetchone()[0]  # noqa: E731
    before, seen = dump_tables(tmp_path / "t.db"), version()

    async def go():
        async with session(base) as s:
            err, got = await call(s, "today")
            assert not err and today_ids(got) == [unreminded["id"]]
            assert trace, "the trace saw no statement at all"
            assert writes() == []
            assert dump_tables(tmp_path / "t.db") == before and version() == seen
            # Control: the same trace and comparison do catch a write when a tool makes one.
            await call(s, "set_star", id=unreminded["id"], starred=True)
            assert any(w.lstrip().upper().startswith("UPDATE ITEMS") for w in writes())
            assert dump_tables(tmp_path / "t.db") != before and version() != seen

    try:
        asyncio.run(go())
    finally:
        watcher.close()
