from __future__ import annotations

import json
import shlex
import sys
import time
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tartib.config import load_settings
from tartib.main import create_app

PASSWORD = "hunter2"
SPACES = "work,home,health,finance,ideas,travel"
FAKE = f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).parent / 'fake_codex.py'))}"
AI_ENV = {"TARTIB_AI_COMMAND": FAKE, "TARTIB_TZ": "Asia/Karachi", "TARTIB_AI_TIMEOUT": "5"}
FAKE_VARS = (
    "FAKE_CODEX_REPLY",
    "FAKE_CODEX_REPLY_CLASSIFY",
    "FAKE_CODEX_REPLY_ASK",
    "FAKE_CODEX_REPLY_TERMS",
    "FAKE_CODEX_REPLY_PICK",
    "FAKE_CODEX_EXIT",
    "FAKE_CODEX_SLEEP",
    "FAKE_CODEX_RECORD",
    "FAKE_CODEX_ERROR",
    "FAKE_CODEX_USAGE",
    "FAKE_CODEX_NO_USAGE",
    "FAKE_CODEX_QUOTA",
)


def make_settings(tmp_path, **extra):
    env = {
        "TARTIB_PASSWORD": PASSWORD,
        "TARTIB_DB_PATH": str(tmp_path / "t.db"),
        "TARTIB_AI_COMMAND": "off",
        "TARTIB_SPACES": SPACES,
    }
    env.update(extra)
    return load_settings(env)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def auth(client) -> TestClient:
    """Authenticated client with AI off: every capture becomes one note in Needs Attention."""
    client.headers["Authorization"] = f"Bearer {PASSWORD}"
    return client


@pytest.fixture
def ai_client(tmp_path, monkeypatch) -> Iterator[TestClient]:
    """Authenticated client whose classifier is the fake Codex script."""
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    with TestClient(create_app(make_settings(tmp_path, **AI_ENV))) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        yield client


# --- helpers shared across test modules ---


def proposal(
    shape="note", text=None, space=None, title=None, due=None, remind_at=None, confidence=0.95
):
    return {
        "shape": shape,
        "text": text,
        "space": space,
        "title": title,
        "due": due,
        "remind_at": remind_at,
        "confidence": confidence,
    }


def set_classify_reply(monkeypatch, *proposals):
    monkeypatch.setenv("FAKE_CODEX_REPLY_CLASSIFY", json.dumps({"proposals": list(proposals)}))


def set_terms_reply(monkeypatch, *terms):
    monkeypatch.setenv("FAKE_CODEX_REPLY_TERMS", json.dumps({"terms": list(terms)}))


def set_ask_reply(monkeypatch, answer="ok", item_ids=()):
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY_ASK", json.dumps({"answer": answer, "item_ids": list(item_ids)})
    )


def wait_capture(client: TestClient, capture_id: int, timeout: float = 8.0) -> dict:
    """Poll until the runner has processed the capture. Returns it with its items."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        cap = client.get(f"/api/captures/{capture_id}").json()
        if cap["status"] != "pending":
            return cap
        time.sleep(0.02)
    raise AssertionError(f"capture {capture_id} never left pending")


def capture(client: TestClient, text: str) -> dict:
    """Capture text and wait for classification. Returns the capture with its items."""
    r = client.post("/api/capture", json={"text": text})
    assert r.status_code == 201, r.text
    return wait_capture(client, r.json()["id"])


def one_item(client: TestClient, text: str) -> dict:
    cap = capture(client, text)
    assert len(cap["items"]) == 1, cap
    return cap["items"][0]


def records(path) -> list[dict]:
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
