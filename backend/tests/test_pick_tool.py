"""`pick` over MCP, and the route it shares its function with (slice 41, step 4).

The AI is `fake_codex_pick.py`, one mode per outcome, so no pick test depends on the
classification steering in `fake_codex.py`."""

from __future__ import annotations

import asyncio
import re
import sqlite3
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import httpx
import pytest

from tartib.store import QUOTA_KEY
from tests import pickfake
from tests.conftest import PASSWORD
from tests.test_mcp import PLAIN_DATE, TODAY_FIELDS, UTC_STAMP, call, session

AUTH = {"Authorization": f"Bearer {PASSWORD}"}
KARACHI = ZoneInfo("Asia/Karachi")
ERROR = "Error executing tool pick: "  # what the SDK puts before a ToolError


@pytest.fixture
def base(tmp_path, monkeypatch):
    url, stop = pickfake.serve(tmp_path, monkeypatch)
    yield url
    stop()


@pytest.fixture
def base_ai_off(tmp_path, monkeypatch):
    url, stop = pickfake.serve(tmp_path, monkeypatch, TARTIB_AI_COMMAND="off")
    yield url
    stop()


def rest(base, method, path, **kw):
    return httpx.request(method, f"{base}{path}", headers=AUTH, timeout=15, **kw)


def make_task(base, text, due=None) -> dict:
    body = {"shape": "task", "space": "work", "text": text}
    if due:
        body["due"] = due
    r = rest(base, "POST", "/api/items", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def thoughts(base, item_id) -> list[str]:
    got = rest(base, "GET", f"/api/items/{item_id}/thoughts").json()["thoughts"]
    return [t["body"] for t in got]


def pick(base):
    async def go():
        async with session(base, token=pickfake.MCP_TOKEN) as s:
            return await call(s, "pick")

    return asyncio.run(go())


def ids(got) -> list[int]:
    return [i["id"] for i in got["items"]]


def tables(tmp_path) -> dict:
    """Every table except what a pick may always write: its `ai_calls` record and the quota."""
    c = sqlite3.connect(tmp_path / "t.db")
    try:
        names = [
            r[0] for r in c.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
                " AND name <> 'ai_calls' ORDER BY name"
            )
        ]
        out = {
            n: sorted((tuple(r) for r in c.execute(f'SELECT * FROM "{n}"')), key=repr)
            for n in names
        }
        out["app_state"] = [r for r in out["app_state"] if r[0] != QUOTA_KEY]
        return out
    finally:
        c.close()


def ai_calls(tmp_path) -> list[tuple]:
    c = sqlite3.connect(tmp_path / "t.db")
    try:
        return c.execute("SELECT kind, ok, failure FROM ai_calls ORDER BY id").fetchall()
    finally:
        c.close()


# --- success ---


def test_a_pick_stars_at_most_three_and_replies_with_exactly_those(base, monkeypatch):
    tasks = [make_task(base, f"Errand {n}") for n in range(5)]
    due = (datetime.now(KARACHI).date() + timedelta(days=9)).isoformat()
    rest(base, "PATCH", f"/api/items/{tasks[0]['id']}", json={"due": due})
    # The dated task is candidate t1; the rest follow in the order they were last touched.
    named = [("t1", "Dated, so first."), ("t3", "  Short\nwin. "), ("t2", "Waited."),
             ("t4", "Fourth."), ("t5", "Fifth.")]
    pickfake.reply(monkeypatch, "success", named)
    err, got = pick(base)
    assert not err
    assert set(got) == {"server_time", "items", "truncated"} and UTC_STAMP.match(got["server_time"])
    assert got["truncated"] is False
    assert ids(got) == [tasks[0]["id"], tasks[2]["id"], tasks[1]["id"]]  # the reply's order
    for item in got["items"]:
        assert set(item) == TODAY_FIELDS
        assert item["starred"] is True and item["space"] == "work"
        assert type(item["id"]) is int and item["remind_at"] is None
    first = got["items"][0]
    assert PLAIN_DATE.match(first["due"]) and first["due"] == due  # read from the database
    assert first["first_line"] == "Errand 0"
    assert thoughts(base, tasks[0]["id"]) == ["Picked for today: Dated, so first."]
    assert thoughts(base, tasks[2]["id"]) == ["Picked for today: Short win."]
    for left_out in tasks[3:]:
        item = rest(base, "GET", f"/api/items/{left_out['id']}").json()
        assert item["starred"] is False and thoughts(base, left_out["id"]) == []
    today = rest(base, "GET", "/api/today").json()["items"]
    assert {i["id"] for i in today} == set(ids(got))


def test_a_second_pick_takes_back_the_first_ones_stars(base, monkeypatch):
    a, b, c = (make_task(base, t) for t in ("A", "B", "C"))
    mine = make_task(base, "Starred by hand")
    rest(base, "PATCH", f"/api/items/{mine['id']}", json={"starred": True})
    pickfake.reply(monkeypatch, "success", [("t1", "First.")])
    err, first = pick(base)
    assert not err and ids(first) == [a["id"]]
    # a was touched by its star, so it is now the last candidate: b is t1.
    pickfake.reply(monkeypatch, "success", [("t1", "Second.")])
    err, second = pick(base)
    assert not err and ids(second) == [b["id"]]  # only what this call starred, not `mine`
    assert second["items"][0]["starred"] is True
    now = {i["id"]: i for i in rest(base, "GET", "/api/today").json()["items"]}
    assert set(now) == {mine["id"], b["id"]}
    assert rest(base, "GET", f"/api/items/{a['id']}").json()["starred"] is False
    assert rest(base, "GET", f"/api/items/{a['id']}").json()["picked_at"] is None
    assert c["id"] not in now


def test_a_mix_of_stale_and_valid_choices_stars_only_the_valid(base, tmp_path, monkeypatch):
    a, b, c = (make_task(base, t) for t in ("A", "B", "C"))
    pickfake.reply(
        monkeypatch, "stale", [("t1", "One."), ("t2", "Two."), ("t3", "Three.")],
        db=tmp_path / "t.db", sql=f"UPDATE items SET status = 'done' WHERE id = {b['id']}",
    )
    err, got = pick(base)
    assert not err and ids(got) == [a["id"], c["id"]]
    assert all(i["starred"] for i in got["items"])
    assert rest(base, "GET", f"/api/items/{b['id']}").json()["starred"] is False
    assert thoughts(base, b["id"]) == []
    assert thoughts(base, a["id"]) == ["Picked for today: One."]


def test_the_tool_sends_no_steer(base, tmp_path, monkeypatch):
    make_task(base, "A")
    record = tmp_path / "calls.jsonl"
    pickfake.reply(monkeypatch, "success", [("t1", "Why.")], record=record)
    err, _ = pick(base)
    assert not err
    prompt = record.read_text()
    assert "The person says: (nothing)" in prompt


# --- an empty list, not an error ---


def test_nothing_to_pick_is_an_empty_list_and_costs_no_call(base, tmp_path, monkeypatch):
    make_task(base, "Overdue already", due="2000-01-01")
    record = tmp_path / "calls.jsonl"
    pickfake.reply(monkeypatch, "success", [("t1", "x")], record=record)
    err, got = pick(base)
    assert not err and got["items"] == [] and got["truncated"] is False
    assert UTC_STAMP.match(got["server_time"])
    assert not record.exists() and ai_calls(tmp_path) == []


def test_picked_tasks_that_changed_meanwhile_are_an_empty_list(base, tmp_path, monkeypatch):
    only = make_task(base, "Only one")
    pickfake.reply(
        monkeypatch, "stale", [("t1", "Gone.")],
        db=tmp_path / "t.db", sql=f"UPDATE items SET status = 'done' WHERE id = {only['id']}",
    )
    err, got = pick(base)
    assert not err and got["items"] == []
    assert thoughts(base, only["id"]) == []
    assert ai_calls(tmp_path) == [("pick", 1, None)]  # the call itself succeeded


# --- an error, and nothing starred ---


def failure_modes():
    return [
        ("failure", [], {"error": "You've hit your usage limit."}, "pick failed: exit 1: "),
        ("junk", [], {}, "pick failed: unusable reply"),
        ("empty", [], {}, "pick failed: the reply named no task"),
        ("success", [("t99", "Not a candidate.")], {}, "pick failed: the reply named no task"),
        ("success", [("t1", "   ")], {}, "pick failed: the reply named no task"),
    ]


@pytest.mark.parametrize(("mode", "picks", "env", "text"), failure_modes())
def test_a_failed_pick_is_an_error_and_every_row_stays_as_it_was(
    base, tmp_path, monkeypatch, mode, picks, env, text
):
    a, b = make_task(base, "A"), make_task(base, "B")
    pickfake.reply(monkeypatch, "success", [("t1", "Earlier pick.")])
    err, first = pick(base)
    assert not err and ids(first) == [a["id"]]
    before = tables(tmp_path)
    calls_before = len(ai_calls(tmp_path))

    pickfake.reply(monkeypatch, mode, picks, **env)
    err, message = pick(base)
    assert err is True and message.startswith(ERROR + text) and len(message) < 400
    assert tables(tmp_path) == before  # every item and thought row, and the rest
    assert rest(base, "GET", f"/api/items/{a['id']}").json()["starred"] is True
    assert thoughts(base, a["id"]) == ["Picked for today: Earlier pick."]
    assert rest(base, "GET", f"/api/items/{b['id']}").json()["starred"] is False
    rows = ai_calls(tmp_path)
    assert len(rows) == calls_before + 1 and rows[-1][0] == "pick" and rows[-1][1] == 0


def test_with_ai_off_the_tool_is_an_error_and_writes_nothing(base_ai_off, tmp_path):
    make_task(base_ai_off, "A")
    before = tables(tmp_path)
    err, message = pick(base_ai_off)
    assert err is True and message == ERROR + "AI not configured"
    assert tables(tmp_path) == before and ai_calls(tmp_path) == []


# --- the route keeps its codes and words ---


def test_the_route_keeps_its_statuses_and_messages(base, base_ai_off, tmp_path, monkeypatch):
    r = rest(base_ai_off, "POST", "/api/pick", json={})
    assert (r.status_code, r.json()["detail"]) == (503, "AI not configured")

    r = rest(base, "POST", "/api/pick", json={})
    assert r.status_code == 200 and r.json() == {
        "picks": [], "message": "Nothing to pick: every open task is already on Today."
    }

    only = make_task(base, "Only one")
    pickfake.reply(monkeypatch, "failure", error="Boom.")
    r = rest(base, "POST", "/api/pick", json={})
    assert r.status_code == 502
    assert re.fullmatch(r"pick failed: exit 1: Boom\.", r.json()["detail"])

    pickfake.reply(monkeypatch, "junk")
    r = rest(base, "POST", "/api/pick", json={})
    assert r.status_code == 502 and r.json()["detail"].startswith("pick failed: unusable reply")

    pickfake.reply(monkeypatch, "empty")
    r = rest(base, "POST", "/api/pick", json={})
    assert (r.status_code, r.json()["detail"]) == (502, "pick failed: the reply named no task")

    pickfake.reply(
        monkeypatch, "stale", [("t1", "Gone.")],
        db=tmp_path / "t.db", sql=f"UPDATE items SET status = 'done' WHERE id = {only['id']}",
    )
    r = rest(base, "POST", "/api/pick", json={})
    assert r.status_code == 200 and r.json() == {
        "picks": [], "message": "The tasks it picked changed meanwhile; pick again."
    }

    second = make_task(base, "Second")
    pickfake.reply(monkeypatch, "success", [("t1", "Do it.")])
    r = rest(base, "POST", "/api/pick", json={})
    assert r.status_code == 200
    [got] = r.json()["picks"]
    assert got["reason"] == "Do it." and got["item"]["id"] == second["id"]
    assert got["item"]["starred"] is True and got["item"]["picked_at"]
