"""What a client that gives up mid-pick does to the Codex child (slice 41, step 3).

Two facts are pinned here. A client that leaves does not cancel the route (Starlette runs a plain
endpoint to the end), so the pick finishes and stars, as the slice's decision 6 expects, and the
child ends by itself or at the call's own timeout. And when something does cancel the call, the
child must die with it: an orphan would outlive its caller with nothing left to time it out."""

from __future__ import annotations

import asyncio
import time

import httpx
import pytest

from tartib.codex import CodexConfig, run_json
from tartib.pick import SCHEMA
from tests import pickfake
from tests.conftest import PASSWORD

AUTH = {"Authorization": f"Bearer {PASSWORD}"}


@pytest.fixture
def pick_server(tmp_path, monkeypatch):
    base, stop = pickfake.serve(tmp_path, monkeypatch)
    yield base
    stop()


@pytest.fixture
def pick_server_short_timeout(tmp_path, monkeypatch):
    base, stop = pickfake.serve(tmp_path, monkeypatch, TARTIB_AI_TIMEOUT="2")
    yield base
    stop()


def make_task(base, text="A") -> dict:
    body = {"shape": "task", "space": "work", "text": text}
    return httpx.post(f"{base}/api/items", headers=AUTH, json=body).json()


def starred(base, item_id) -> bool:
    return httpx.get(f"{base}/api/items/{item_id}", headers=AUTH).json()["starred"]


def leave_mid_pick(base, wait_for_pid) -> None:
    """Start a pick, hold on until Codex is running, then drop the connection."""
    with httpx.Client(headers=AUTH, timeout=0.8) as client:
        with pytest.raises(httpx.ReadTimeout):
            client.post(f"{base}/api/pick", json={})
    assert wait_for_pid() is not None


def waiter(pidfile):
    def wait():
        for _ in range(100):
            if pickfake.pid_of(pidfile) is not None:
                break
            time.sleep(0.05)
        return pickfake.pid_of(pidfile)

    return wait


def until_dead(pid, seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and pickfake.alive(pid):
        time.sleep(0.05)
    return not pickfake.alive(pid)


def test_a_pick_whose_client_left_still_finishes_and_leaves_no_process(
    pick_server, tmp_path, monkeypatch
):
    task = make_task(pick_server)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=2.5, pidfile=pidfile)
    leave_mid_pick(pick_server, waiter(pidfile))
    pid = pickfake.pid_of(pidfile)
    try:
        # The route was not cancelled: Codex is still working after the client has gone ...
        assert pickfake.alive(pid) and not starred(pick_server, task["id"])
        # ... it finishes, the pick lands, and nothing is left running.
        assert until_dead(pid, 6)
        for _ in range(40):
            if starred(pick_server, task["id"]):
                break
            time.sleep(0.05)
        assert starred(pick_server, task["id"]) is True
    finally:
        pickfake.kill_if_alive(pid)


def test_a_hung_codex_is_killed_at_the_calls_own_timeout(
    pick_server_short_timeout, tmp_path, monkeypatch
):
    base = pick_server_short_timeout
    task = make_task(base)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=30, pidfile=pidfile)
    leave_mid_pick(base, waiter(pidfile))
    pid = pickfake.pid_of(pidfile)
    try:
        assert until_dead(pid, 6)  # AI timeout is 2s; the fake would sleep for 30
        assert starred(base, task["id"]) is False
    finally:
        pickfake.kill_if_alive(pid)


def test_cancelling_a_codex_call_stops_its_child(tmp_path, monkeypatch):
    pickfake.clear(monkeypatch)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=30, pidfile=pidfile)
    cfg = CodexConfig(command=pickfake.COMMAND, timeout=60)

    async def go():
        call = asyncio.create_task(run_json("You pick what", SCHEMA, cfg))
        for _ in range(100):
            if pickfake.pid_of(pidfile) is not None:
                break
            await asyncio.sleep(0.05)
        call.cancel()
        # The fake sleeps for 30s. Cancellation must end the call at once: if the child were not
        # killed, the call would wait for it and this bound would run out.
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(call, timeout=5)

    started = time.monotonic()
    asyncio.run(go())
    assert time.monotonic() - started < 10
    pid = pickfake.pid_of(pidfile)
    try:
        assert pid is not None and not pickfake.alive(pid)
    finally:
        pickfake.kill_if_alive(pid)


def test_cancelling_after_the_child_has_exited_still_raises_cancelled(tmp_path, monkeypatch):
    """The cancel lands just after the child ended: killing it finds nothing, and that must not
    replace the cancellation."""
    pickfake.clear(monkeypatch)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=0, pidfile=pidfile)
    cfg = CodexConfig(command=pickfake.COMMAND, timeout=60)
    real_wait_for = asyncio.wait_for

    async def cancelled_after_exit(aw, timeout=None):
        await real_wait_for(aw, timeout)  # the child runs to its end and is reaped
        raise asyncio.CancelledError

    monkeypatch.setattr(asyncio, "wait_for", cancelled_after_exit)

    async def go():
        with pytest.raises(asyncio.CancelledError):
            await run_json("You pick what", SCHEMA, cfg)

    asyncio.run(go())
    pid = pickfake.pid_of(pidfile)
    try:
        assert pid is not None and not pickfake.alive(pid)
    finally:
        pickfake.kill_if_alive(pid)


def leave_mid_mcp_pick(base, wait_for_pid) -> None:
    """The same, through the MCP tool: the client's wait runs out and its connection closes."""
    from mcp.shared.exceptions import MCPError

    from tests.test_mcp import session

    async def go():
        async with session(base, token=pickfake.MCP_TOKEN) as s:
            with pytest.raises(MCPError):
                await s.call_tool("pick", {}, read_timeout_seconds=0.8)

    asyncio.run(go())
    assert wait_for_pid() is not None


def test_an_mcp_client_that_gives_up_leaves_the_same_picture(pick_server, tmp_path, monkeypatch):
    task = make_task(pick_server)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=2.5, pidfile=pidfile)
    leave_mid_mcp_pick(pick_server, waiter(pidfile))
    pid = pickfake.pid_of(pidfile)
    try:
        assert pickfake.alive(pid) and not starred(pick_server, task["id"])
        assert until_dead(pid, 6)
        for _ in range(40):
            if starred(pick_server, task["id"]):
                break
            time.sleep(0.05)
        assert starred(pick_server, task["id"]) is True
    finally:
        pickfake.kill_if_alive(pid)


def test_a_hung_codex_behind_an_mcp_call_is_killed_at_the_timeout(
    pick_server_short_timeout, tmp_path, monkeypatch
):
    base = pick_server_short_timeout
    task = make_task(base)
    pidfile = tmp_path / "pid"
    pickfake.reply(monkeypatch, "sleep", [("t1", "Why.")], seconds=30, pidfile=pidfile)
    leave_mid_mcp_pick(base, waiter(pidfile))
    pid = pickfake.pid_of(pidfile)
    try:
        assert until_dead(pid, 6)
        assert starred(base, task["id"]) is False
    finally:
        pickfake.kill_if_alive(pid)
