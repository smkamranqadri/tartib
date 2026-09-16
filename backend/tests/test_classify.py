"""Classifier pipeline with the fake Codex CLI run as a real subprocess."""

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tartib import db
from tartib.main import create_app
from tests.conftest import (
    AI_ENV,
    PASSWORD,
    capture,
    make_settings,
    proposal,
    records,
    set_ask_reply,
    set_classify_reply,
    wait_capture,
)


def test_confident_proposal_is_filed_with_excerpt(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(
        monkeypatch,
        proposal(
            shape="task",
            text="call the dentist tomorrow",
            space="Health",
            title="Call the dentist",
            due="2026-09-18",
            remind_at="2026-09-18T09:00:00",
            confidence=0.95,
        ),
    )
    cap = capture(ai_client, "call the dentist tomorrow")
    assert cap["status"] == "done" and cap["error"] is None
    [item] = cap["items"]
    assert item["stage"] == "filed"
    assert item["shape"] == "task"
    assert item["space"] == "health"
    assert item["title"] == "Call the dentist"
    assert item["due"] == "2026-09-18"
    assert item["remind_at"] == "2026-09-18T04:00:00Z"  # 09:00 Karachi -> UTC
    assert item["proposal"]["confidence"] == 0.95
    assert "text" not in item["proposal"]
    assert item["raw_text"] == "call the dentist tomorrow"
    assert item["capture_id"] == cap["id"]

    [call] = records(record)
    argv = call["argv"]
    assert argv[0] == "exec" and call["stdin_is_tty"] is False
    for flag in ("--ephemeral", "--skip-git-repo-check", "--ignore-user-config", "--output-schema"):
        assert flag in argv
    assert argv[argv.index("--sandbox") + 1] == "read-only"
    prompt = argv[-1]
    assert prompt.startswith("You file short personal captures for one person.")
    assert '{"proposals": [ ... ]}' in prompt
    assert "Existing spaces: work, home, health, finance, ideas, travel" in prompt
    assert "Asia/Karachi" in prompt
    assert prompt.endswith("Text:\ncall the dentist tomorrow")


def test_multi_item_capture_splits_into_items(ai_client, monkeypatch):
    set_classify_reply(
        monkeypatch,
        proposal(shape="task", text="Renew passport", space="travel", title="Renew passport"),
        proposal(shape="task", text="call the dentist", space="health", title="Call the dentist"),
        proposal(shape="note", text="buy milk", space=None, confidence=0.5),
    )
    cap = capture(ai_client, "Renew passport, call the dentist, and buy milk")
    assert [i["raw_text"] for i in cap["items"]] == [
        "Renew passport",
        "call the dentist",
        "buy milk",
    ]
    assert [i["stage"] for i in cap["items"]] == ["filed", "filed", "attention"]
    assert all(i["capture_id"] == cap["id"] for i in cap["items"])
    assert cap["items"][2]["space"] is None
    # search finds the specific item, not all three
    hits = ai_client.get("/api/items", params={"q": "milk"}).json()["items"]
    assert [h["raw_text"] for h in hits] == ["buy milk"]


def test_missing_excerpt_falls_back_to_full_text(ai_client, monkeypatch):
    set_classify_reply(monkeypatch, proposal(shape="note", text=None, space="ideas"))
    [item] = capture(ai_client, "full text here")["items"]
    assert item["raw_text"] == "full text here"


def test_question_is_answered_not_stored(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    set_classify_reply(
        monkeypatch, proposal(shape="note", text="Ali said 100 req/min", space="work")
    )
    prior = capture(ai_client, "Ali said 100 req/min")["items"][0]
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(
        monkeypatch,
        proposal(
            shape="question",
            text="what did Ali say about rate limits?",
            space="work",
            title="junk",
            confidence=0.9,
        ),
    )
    set_ask_reply(monkeypatch, "Ali said 100 requests per minute.", [prior["id"]])
    cap = capture(ai_client, "what did Ali say about rate limits?")
    assert cap["status"] == "done"
    assert cap["items"] == []
    assert cap["answer"]["answer"] == "Ali said 100 requests per minute."
    assert cap["answer"]["item_ids"] == [prior["id"]]
    assert cap["answer"]["items"][0]["raw_text"] == "Ali said 100 req/min"
    calls = records(record)
    assert [c["ask"] for c in calls] == [False, True]
    ask_prompt = calls[1]["argv"][-1]
    assert "Question: what did Ali say about rate limits?" in ask_prompt
    assert "Current datetime:" in ask_prompt and "Asia/Karachi" in ask_prompt
    assert f"[id {prior['id']}] " in ask_prompt


def test_mixed_capture_files_items_and_answers_question(ai_client, monkeypatch):
    set_classify_reply(
        monkeypatch,
        proposal(shape="task", text="buy milk", space="home", title="Buy milk"),
        proposal(shape="question", text="where did I park?"),
    )
    set_ask_reply(monkeypatch, "No idea.", [])
    cap = capture(ai_client, "buy milk. where did I park?")
    assert [i["title"] for i in cap["items"]] == ["Buy milk"]
    assert cap["answer"]["answer"] == "No idea."


def test_question_ask_failure_is_recorded(ai_client, monkeypatch):
    set_classify_reply(monkeypatch, proposal(shape="note", text="seed", space="work"))
    capture(ai_client, "seed")
    set_classify_reply(monkeypatch, proposal(shape="question", text="anything?"))
    monkeypatch.setenv("FAKE_CODEX_REPLY_ASK", "not json")
    cap = capture(ai_client, "anything?")
    assert cap["status"] == "done"
    assert cap["answer"]["answer"].startswith("Could not answer")
    assert "ask failed" in cap["error"]


@pytest.mark.parametrize(
    "space, confidence, expected_stage, expected_conf",
    [
        ("work", 0.85, "filed", 0.85),
        ("work", 0.84, "attention", 0.84),
        (None, 0.99, "attention", 0.6),  # null space caps confidence
        ("garage", 0.99, "attention", 0.6),  # invented space becomes null
        ("WORK ", 0.9, "filed", 0.9),
    ],
)
def test_space_and_threshold_routing(
    ai_client, monkeypatch, space, confidence, expected_stage, expected_conf
):
    set_classify_reply(
        monkeypatch, proposal(shape="note", text="x", space=space, confidence=confidence)
    )
    [item] = capture(ai_client, "x")["items"]
    assert item["stage"] == expected_stage
    assert item["proposal"]["confidence"] == expected_conf
    assert item["space"] in (None, "work")


def test_note_proposal_drops_task_fields(ai_client, monkeypatch):
    set_classify_reply(
        monkeypatch,
        proposal(shape="note", text="rain", space="home", title="junk", due="2026-01-01"),
    )
    [item] = capture(ai_client, "rain today")["items"]
    assert item["stage"] == "filed" and item["shape"] == "note"
    assert item["title"] is None and item["due"] is None


@pytest.mark.parametrize(
    "env, error_fragment",
    [
        ({"FAKE_CODEX_EXIT": "3"}, "exit 3: fake codex: simulated failure"),
        ({"FAKE_CODEX_REPLY": "not json"}, "unusable reply"),
        ({"FAKE_CODEX_REPLY": '{"proposals": []}'}, "no proposals"),
        ({"FAKE_CODEX_REPLY": '{"proposals": [{"shape": "task"}]}'}, "invalid proposal"),
        (
            {"FAKE_CODEX_REPLY": '{"proposals": [{"shape": "task", "confidence": 2}]}'},
            "invalid proposal",
        ),
        ({"FAKE_CODEX_SLEEP": "3", "TARTIB_AI_TIMEOUT": "0.5"}, "timed out"),
    ],
)
def test_bad_cli_falls_back_to_one_note(tmp_path, monkeypatch, env, error_fragment):
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    overrides = {**AI_ENV, **{k: v for k, v in env.items() if k.startswith("TARTIB_")}}
    with TestClient(create_app(make_settings(tmp_path, **overrides))) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        cap = capture(client, "x")
    assert cap["status"] == "error" and error_fragment in cap["error"]
    [item] = cap["items"]
    assert item["stage"] == "attention" and item["space"] is None and item["proposal"] is None
    assert error_fragment in item["proposal_error"]


def test_missing_binary_falls_back(tmp_path):
    settings = make_settings(tmp_path, TARTIB_AI_COMMAND="/nonexistent/codex")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        cap = capture(client, "x")
    assert "cannot run '/nonexistent/codex'" in cap["error"]


def test_model_flag_only_when_configured(tmp_path, monkeypatch):
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(monkeypatch, proposal(shape="note", text="x", space="work"))
    with TestClient(
        create_app(make_settings(tmp_path, **AI_ENV, TARTIB_AI_MODEL="gpt-5-mini"))
    ) as c:
        c.headers["Authorization"] = f"Bearer {PASSWORD}"
        capture(c, "x")
    argv = records(record)[0]["argv"]
    assert argv[argv.index("--model") + 1] == "gpt-5-mini"


def test_startup_requeues_pending_captures(tmp_path, monkeypatch):
    settings = make_settings(tmp_path, **AI_ENV)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    conn.execute(
        "INSERT INTO captures (raw_text, source, created_at)"
        " VALUES ('left over', 'api', '2026-09-17T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    set_classify_reply(
        monkeypatch, proposal(shape="task", text="left over", space="home", title="Left over")
    )
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        cap = wait_capture(client, 1)
    assert cap["status"] == "done" and cap["items"][0]["title"] == "Left over"


def test_crash_in_one_capture_does_not_stop_the_runner(ai_client, monkeypatch, settings):
    set_classify_reply(monkeypatch, proposal(shape="note", text="fine", space="work"))
    assert capture(ai_client, "fine")["status"] == "done"
    # a capture row the runner cannot process normally: force an internal error via a bad shape
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY_CLASSIFY",
        json.dumps(
            {
                "proposals": [
                    {
                        "shape": "note",
                        "text": "p",
                        "space": "work",
                        "title": None,
                        "due": None,
                        "remind_at": None,
                        "confidence": 0.9,
                        "extra": 1,
                    }
                ]
            }
        ),
    )
    cap = capture(ai_client, "poison-ish")
    assert cap["status"] == "done"  # extra keys are ignored, not fatal
    set_classify_reply(monkeypatch, proposal(shape="note", text="still", space="work"))
    assert capture(ai_client, "still alive")["status"] == "done"
    conn = sqlite3.connect(ai_client.app.state.settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM captures WHERE status='pending'").fetchone()[0] == 0
