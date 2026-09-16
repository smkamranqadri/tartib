"""Classify adapter and background runner, driving a fake Codex CLI as a real subprocess."""

import json
import shlex
import sqlite3
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tartib import db
from tartib.main import create_app
from tests.conftest import PASSWORD, make_settings

FAKE = f"{shlex.quote(sys.executable)} {shlex.quote(str(Path(__file__).parent / 'fake_codex.py'))}"
AI_ENV = {"TARTIB_AI_COMMAND": FAKE, "TARTIB_TZ": "Asia/Karachi", "TARTIB_AI_TIMEOUT": "5"}


def reply(monkeypatch, **fields):
    monkeypatch.setenv("FAKE_CODEX_REPLY", json.dumps(fields))


def wait_classified(client: TestClient, item_id: int, timeout: float = 8.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = client.get(f"/api/items/{item_id}").json()
        if item["stage"] != "inbox":
            return item
        time.sleep(0.02)
    raise AssertionError(f"item {item_id} never left inbox")


@pytest.fixture
def ai_client(tmp_path, monkeypatch):
    for var in ("FAKE_CODEX_REPLY", "FAKE_CODEX_EXIT", "FAKE_CODEX_SLEEP", "FAKE_CODEX_RECORD"):
        monkeypatch.delenv(var, raising=False)
    with TestClient(create_app(make_settings(tmp_path, **AI_ENV))) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        yield client


def test_confident_proposal_is_filed(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    reply(
        monkeypatch,
        shape="task",
        space="Health ",
        title="Call the dentist",
        due="2026-09-18",
        remind_at="2026-09-18T09:00:00",
        confidence=0.95,
    )
    r = ai_client.post("/api/capture", json={"text": "call the dentist tomorrow"})
    item = wait_classified(ai_client, r.json()["id"])
    assert item["stage"] == "filed"
    assert item["shape"] == "task"
    assert item["space"] == "health"
    assert item["title"] == "Call the dentist"
    assert item["due"] == "2026-09-18"
    # naive 09:00 in Asia/Karachi (UTC+5) is stored as 04:00Z
    assert item["remind_at"] == "2026-09-18T04:00:00Z"
    assert item["proposal"]["confidence"] == 0.95
    assert item["raw_text"] == "call the dentist tomorrow"

    sent = json.loads(record.read_text())
    argv = sent["argv"]
    assert argv[0] == "exec"
    for flag in ("--ephemeral", "--skip-git-repo-check", "--ignore-user-config", "--output-schema"):
        assert flag in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    assert "call the dentist tomorrow" in argv[-1]
    assert "Asia/Karachi" in argv[-1]
    assert sent["stdin_is_tty"] is False
    # the per-call temp dir (schema, reply, workdir) is gone once classify returns
    assert not Path(argv[argv.index("--output-schema") + 1]).exists()


def test_model_flag_only_when_configured(tmp_path, monkeypatch):
    record = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    reply(monkeypatch, shape="note", space="x", confidence=0.9)
    settings = make_settings(tmp_path, **AI_ENV, TARTIB_AI_MODEL="gpt-5-mini")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        item_id = client.post("/api/capture", json={"text": "x"}).json()["id"]
        wait_classified(client, item_id)
    argv = json.loads(record.read_text())["argv"]
    assert argv[argv.index("--model") + 1] == "gpt-5-mini"


def test_unsure_proposal_needs_attention(ai_client, monkeypatch):
    reply(monkeypatch, shape="note", space="ideas", confidence=0.4)
    item_id = ai_client.post("/api/capture", json={"text": "something vague"}).json()["id"]
    item = wait_classified(ai_client, item_id)
    assert item["stage"] == "attention"
    assert item["space"] == "inbox"  # not applied yet
    assert item["proposal"] == {
        "shape": "note",
        "space": "ideas",
        "title": None,
        "due": None,
        "remind_at": None,
        "confidence": 0.4,
    }
    assert item["proposal_error"] is None


def test_note_proposal_drops_task_fields(ai_client, monkeypatch):
    reply(monkeypatch, shape="note", space="log", title="junk", due="2026-01-01", confidence=0.99)
    item_id = ai_client.post("/api/capture", json={"text": "rain today"}).json()["id"]
    item = wait_classified(ai_client, item_id)
    assert item["stage"] == "filed"
    assert item["shape"] == "note"
    assert item["title"] is None and item["due"] is None


@pytest.mark.parametrize(
    "env, error_fragment",
    [
        ({"FAKE_CODEX_EXIT": "3"}, "exit 3: fake codex: simulated failure"),
        ({"FAKE_CODEX_REPLY": "not json"}, "unusable reply"),
        ({"FAKE_CODEX_REPLY": '{"shape": "task", "confidence": 1.7}'}, "invalid proposal"),
        ({"FAKE_CODEX_REPLY": '{"shape": "task"}'}, "invalid proposal"),
        ({"FAKE_CODEX_SLEEP": "3", "TARTIB_AI_TIMEOUT": "0.5"}, "timed out"),
    ],
)
def test_bad_cli_goes_to_attention(tmp_path, monkeypatch, env, error_fragment):
    for var in ("FAKE_CODEX_REPLY", "FAKE_CODEX_EXIT", "FAKE_CODEX_SLEEP"):
        monkeypatch.delenv(var, raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    overrides = {**AI_ENV, **{k: v for k, v in env.items() if k.startswith("TARTIB_")}}
    with TestClient(create_app(make_settings(tmp_path, **overrides))) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        item_id = client.post("/api/capture", json={"text": "x"}).json()["id"]
        item = wait_classified(client, item_id)
    assert item["stage"] == "attention"
    assert item["proposal"] is None
    assert error_fragment in item["proposal_error"]


def test_missing_binary_goes_to_attention(tmp_path):
    settings = make_settings(tmp_path, TARTIB_AI_COMMAND="/nonexistent/codex")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        item_id = client.post("/api/capture", json={"text": "x"}).json()["id"]
        item = wait_classified(client, item_id)
    assert item["stage"] == "attention"
    assert "cannot run '/nonexistent/codex'" in item["proposal_error"]


def test_ai_off_goes_to_attention(auth):
    item_id = auth.post("/api/capture", json={"text": "x"}).json()["id"]
    item = wait_classified(auth, item_id)
    assert item["stage"] == "attention"
    assert item["proposal_error"] == "AI not configured"


def test_startup_requeues_inbox_items(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, **AI_ENV)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    conn.execute(
        "INSERT INTO items (raw_text, created_at) VALUES ('left over', '2026-09-17T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    reply(monkeypatch, shape="task", space="home", title="Left over", confidence=0.9)
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        item = wait_classified(client, 1)
    assert item["stage"] == "filed"
    assert item["title"] == "Left over"


def test_existing_spaces_are_sent_as_context(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "argv.json"
    reply(monkeypatch, shape="note", space="work", confidence=0.9)
    first = ai_client.post("/api/capture", json={"text": "one"}).json()["id"]
    wait_classified(ai_client, first)
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    second = ai_client.post("/api/capture", json={"text": "two"}).json()["id"]
    wait_classified(ai_client, second)
    prompt = json.loads(record.read_text())["argv"][-1]
    assert "Existing spaces: work" in prompt


def test_crash_in_one_item_does_not_stop_the_runner(ai_client, monkeypatch):
    reply(monkeypatch, shape="note", space="a", confidence=0.9)
    ok = ai_client.post("/api/capture", json={"text": "fine"}).json()["id"]
    assert wait_classified(ai_client, ok)["stage"] == "filed"
    conn = sqlite3.connect(ai_client.app.state.settings.db_path)
    conn.execute(
        "INSERT INTO items (raw_text, created_at) VALUES ('poison', '2026-09-17T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    poison = ai_client.get("/api/items/2").json()["id"]
    reply(monkeypatch, shape="task", space="x" * 500, confidence=0.9)
    ai_client.app.state.runner.enqueue(poison)
    wait_classified(ai_client, poison)
    reply(monkeypatch, shape="note", space="a", confidence=0.9)
    after = ai_client.post("/api/capture", json={"text": "still alive"}).json()["id"]
    assert wait_classified(ai_client, after)["stage"] == "filed"
