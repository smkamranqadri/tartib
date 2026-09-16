"""POST /api/ask: retrieval, fallback, prompt content, and the answer contract."""

import json

import pytest
from fastapi.testclient import TestClient

from tartib.ask import retrieval_query
from tartib.main import create_app
from tests.conftest import PASSWORD, make_settings
from tests.test_classify import AI_ENV, wait_classified


@pytest.mark.parametrize(
    "q, expected",
    [
        ("what did I decide about the database?", '"database"*'),
        ("Postgres or SQLite?", '"postgres"* OR "sqlite"*'),
        ("gym", '"gym"'),
        ("what did I say?", ""),
        ("", ""),
        ("2026 plans", '"2026"* OR "plans"*'),
    ],
)
def test_retrieval_query(q, expected):
    assert retrieval_query(q) == expected


@pytest.fixture
def ai_client(tmp_path, monkeypatch):
    for var in ("FAKE_CODEX_REPLY", "FAKE_CODEX_EXIT", "FAKE_CODEX_SLEEP", "FAKE_CODEX_RECORD"):
        monkeypatch.delenv(var, raising=False)
    with TestClient(create_app(make_settings(tmp_path, **AI_ENV))) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        yield client


def seed(client, monkeypatch, texts):
    """Capture each text and file it as a note in the given space via the fake classifier."""
    ids = []
    for space, text in texts:
        monkeypatch.setenv(
            "FAKE_CODEX_REPLY", json.dumps({"shape": "note", "space": space, "confidence": 0.99})
        )
        item_id = client.post("/api/capture", json={"text": text}).json()["id"]
        wait_classified(client, item_id)
        ids.append(item_id)
    return ids


def test_ask_retrieves_matches_and_cites(ai_client, monkeypatch, tmp_path):
    db_id, gym_id, _ = seed(
        ai_client,
        monkeypatch,
        [
            ("work", "Decided: use SQLite with FTS5 for Tartib, no Postgres."),
            ("health", "Gym on Tuesdays and Fridays, mornings."),
            ("work", "Standup moved to 10:30."),
        ],
    )
    record = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY",
        json.dumps({"answer": "You chose SQLite with FTS5.", "item_ids": [db_id, 999, db_id]}),
    )
    r = ai_client.post("/api/ask", json={"question": "what did I decide about sqlite vs postgres?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "You chose SQLite with FTS5."
    assert body["item_ids"] == [db_id]  # unknown and duplicate ids dropped
    assert body["items"][0]["id"] == db_id
    assert body["items"][0]["raw_text"].startswith("Decided: use SQLite")
    assert body["matched"] is True
    prompt = json.loads(record.read_text())["argv"][-1]
    assert f"[id {db_id}]" in prompt and "SQLite with FTS5" in prompt
    assert f"[id {gym_id}]" not in prompt  # only FTS matches are sent
    assert "what did I decide about sqlite vs postgres?" in prompt


def test_ask_falls_back_to_recent_in_space(ai_client, monkeypatch, tmp_path):
    ids = seed(
        ai_client,
        monkeypatch,
        [("work", "alpha note"), ("home", "beta note"), ("work", "gamma note")],
    )
    record = tmp_path / "argv.json"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY", json.dumps({"answer": "Nothing on that.", "item_ids": []})
    )
    r = ai_client.post("/api/ask", json={"question": "zzzz unknown", "space": "Work"})
    assert r.status_code == 200
    assert r.json()["matched"] is False
    assert r.json()["item_ids"] == []
    prompt = json.loads(record.read_text())["argv"][-1]
    assert f"[id {ids[0]}]" in prompt and f"[id {ids[2]}]" in prompt
    assert f"[id {ids[1]}]" not in prompt  # other space excluded


def test_ask_is_read_only(ai_client, monkeypatch):
    ids = seed(ai_client, monkeypatch, [("work", "immutable thing")])
    before = ai_client.get(f"/api/items/{ids[0]}").json()
    monkeypatch.setenv("FAKE_CODEX_REPLY", json.dumps({"answer": "x", "item_ids": ids}))
    ai_client.post("/api/ask", json={"question": "immutable"})
    assert ai_client.get(f"/api/items/{ids[0]}").json() == before


def test_ask_with_no_items(ai_client, monkeypatch):
    r = ai_client.post("/api/ask", json={"question": "anything"})
    assert r.status_code == 200
    assert r.json() == {
        "answer": "There are no items to answer from yet.",
        "item_ids": [],
        "items": [],
        "matched": False,
    }
    seed(ai_client, monkeypatch, [("work", "something")])
    r = ai_client.post("/api/ask", json={"question": "anything", "space": "empty-space"})
    assert r.status_code == 200 and r.json()["matched"] is False and r.json()["items"] == []


def test_ask_errors(ai_client, monkeypatch, auth):
    seed(ai_client, monkeypatch, [("work", "something")])
    monkeypatch.setenv("FAKE_CODEX_EXIT", "2")
    r = ai_client.post("/api/ask", json={"question": "something"})
    assert r.status_code == 502
    assert "ask failed" in r.json()["detail"]
    assert ai_client.post("/api/ask", json={"question": "   "}).status_code == 422
    # `auth` is a client with AI off
    assert auth.post("/api/ask", json={"question": "x"}).status_code == 503
