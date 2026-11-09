"""Helpers for tests that run Pick against `fake_codex_pick.py` (slice 41)."""

from __future__ import annotations

import json
import os
import shlex
import socket
import sys
import threading
import time
from pathlib import Path

import httpx
import uvicorn

from tartib.main import create_app
from tests.conftest import AI_ENV, FAKE_VARS, make_settings

MCP_TOKEN = "mcp-test-token-long-enough-to-be-accepted"

COMMAND = (
    f"{shlex.quote(sys.executable)} "
    f"{shlex.quote(str(Path(__file__).parent / 'fake_codex_pick.py'))}"
)
VARS = (
    "FAKE_PICK_MODE",
    "FAKE_PICK_PICKS",
    "FAKE_PICK_DB",
    "FAKE_PICK_SQL",
    "FAKE_PICK_SECONDS",
    "FAKE_PICK_ERROR",
    "FAKE_PICK_PIDFILE",
    "FAKE_PICK_RECORD",
)


def clear(monkeypatch) -> None:
    for var in VARS:
        monkeypatch.delenv(var, raising=False)


def reply(monkeypatch, mode: str = "success", picks=(), **env) -> None:
    """Set what the next pick call does. `env` keys are the FAKE_PICK_* names without prefix."""
    monkeypatch.setenv("FAKE_PICK_MODE", mode)
    monkeypatch.setenv("FAKE_PICK_PICKS", json.dumps([list(p) for p in picks]))
    for key, value in env.items():
        monkeypatch.setenv(f"FAKE_PICK_{key.upper()}", str(value))


def alive(pid: int) -> bool:
    """Whether the process is still running (a zombie is not)."""
    try:
        state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
    except (FileNotFoundError, ProcessLookupError):
        return False
    return state not in ("Z", "X")


def pid_of(pidfile: Path) -> int | None:
    try:
        return int(pidfile.read_text())
    except (FileNotFoundError, ValueError):
        return None


def kill_if_alive(pid: int | None) -> None:
    if pid is not None and alive(pid):
        os.kill(pid, 9)


def serve(tmp_path, monkeypatch, **extra):
    """The app under uvicorn with MCP on and the pick fake as its AI. Returns (base, stop)."""
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    clear(monkeypatch)
    env = {**AI_ENV, "TARTIB_AI_COMMAND": COMMAND, "TARTIB_MCP_TOKEN": MCP_TOKEN, **extra}
    app = create_app(make_settings(tmp_path, **env))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
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

    def stop() -> None:
        server.should_exit = True
        thread.join(timeout=10)

    return base, stop
