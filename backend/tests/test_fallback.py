"""When Codex fails, the Claude CLI answers. Both fakes are real subprocesses."""

import json

from fastapi.testclient import TestClient

from tartib.codex import dialect
from tartib.main import create_app
from tests.conftest import (
    AI_ENV,
    FAKE_CLAUDE,
    PASSWORD,
    capture,
    make_settings,
    proposal,
    records,
    set_classify_reply,
)


def test_dialect():
    assert dialect("codex") == "codex"
    assert dialect("/usr/local/bin/claude") == "claude"
    assert dialect("python3 /x/fake_claude.py") == "claude"
    assert dialect("python3 /x/fake_codex.py") == "codex"


def fallback_client(tmp_path, **extra):
    """A TestClient (use as a context manager) whose fallback is the fake Claude CLI."""
    settings = make_settings(tmp_path, **AI_ENV, TARTIB_AI_FALLBACK_COMMAND=FAKE_CLAUDE, **extra)
    client = TestClient(create_app(settings))
    client.headers["Authorization"] = f"Bearer {PASSWORD}"
    return client


def test_fallback_classifies_when_codex_fails(tmp_path, monkeypatch):
    codex_rec, claude_rec = tmp_path / "codex.jsonl", tmp_path / "claude.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(codex_rec))
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(claude_rec))
    monkeypatch.setenv("FAKE_CODEX_EXIT", "1")  # e.g. usage limit
    monkeypatch.setenv("CLAUDECODE", "1")  # as if started from inside a Claude Code session
    monkeypatch.setenv(
        "FAKE_CLAUDE_REPLY_CLASSIFY",
        json.dumps({"proposals": [proposal(shape="task", text="x", space="home", title="X")]}),
    )
    with fallback_client(tmp_path, TARTIB_AI_FALLBACK_MODEL="haiku") as client:
        assert client.get("/api/health").json()["fallback"] is True
        cap = capture(client, "x")
    assert cap["status"] == "done" and cap["error"] is None
    [item] = cap["items"]
    assert item["stage"] == "filed" and item["title"] == "X"
    assert len(records(codex_rec)) == 1
    [call] = records(claude_rec)
    argv = call["argv"]
    assert argv[0] == "--print"
    assert argv[argv.index("--output-format") + 1] == "json"
    assert json.loads(argv[argv.index("--json-schema") + 1])["required"] == ["proposals"]
    assert argv[argv.index("--tools") + 1] == ""
    assert argv[argv.index("--model") + 1] == "haiku"
    assert argv[-1].startswith("You file short personal captures")
    assert call["claudecode"] is False


def test_fallback_not_used_when_codex_succeeds(tmp_path, monkeypatch):
    claude_rec = tmp_path / "claude.jsonl"
    monkeypatch.setenv("FAKE_CLAUDE_RECORD", str(claude_rec))
    set_classify_reply(monkeypatch, proposal(shape="note", text="x", space="work"))
    with fallback_client(tmp_path) as client:
        cap = capture(client, "x")
    assert cap["status"] == "done"
    assert not claude_rec.exists()


def test_both_fail_reports_both(tmp_path, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_EXIT", "1")
    monkeypatch.setenv("FAKE_CLAUDE_IS_ERROR", "Not logged in · Please run /login")
    with fallback_client(tmp_path) as client:
        cap = capture(client, "x")
    assert cap["status"] == "error"
    assert "exit 1: fake codex" in cap["error"]
    assert "fallback: claude error: Not logged in" in cap["error"]
    assert cap["items"][0]["stage"] == "attention"


def test_fallback_answers_questions_too(tmp_path, monkeypatch):
    set_classify_reply(monkeypatch, proposal(shape="note", text="seed", space="work"))
    with fallback_client(tmp_path) as client:
        seed = capture(client, "seed")["items"][0]
        monkeypatch.setenv("FAKE_CODEX_EXIT", "1")
        monkeypatch.setenv(
            "FAKE_CLAUDE_REPLY_CLASSIFY",
            json.dumps({"proposals": [proposal(shape="question", text="seed?")]}),
        )
        monkeypatch.setenv(
            "FAKE_CLAUDE_REPLY_ASK",
            json.dumps({"answer": "From Claude.", "item_ids": [seed["id"]]}),
        )
        cap = capture(client, "seed?")
        assert cap["answer"]["answer"] == "From Claude." and cap["answer"]["item_ids"] == [
            seed["id"]
        ]
        r = client.post("/api/ask", json={"question": "seed"})
        assert r.json()["answer"] == "From Claude."
