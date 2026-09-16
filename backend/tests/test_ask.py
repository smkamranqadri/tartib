"""POST /api/ask: retrieval, fallback, prompt content, and the answer contract."""

import json

import pytest

from tartib.ask import retrieval_query
from tests.conftest import capture, proposal, records, set_ask_reply, set_classify_reply


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


def seed(client, monkeypatch, texts):
    """Capture each text and file it as a note in the given space via the fake classifier."""
    ids = []
    for space, text in texts:
        set_classify_reply(monkeypatch, proposal(shape="note", text=text, space=space))
        ids.append(capture(client, text)["items"][0]["id"])
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
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "You chose SQLite with FTS5.", [db_id, 999, db_id])
    r = ai_client.post("/api/ask", json={"question": "what did I decide about sqlite vs postgres?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "You chose SQLite with FTS5."
    assert body["item_ids"] == [db_id]  # unknown and duplicate ids dropped
    assert body["items"][0]["id"] == db_id
    assert body["matched"] is True
    prompt = records(record)[-1]["argv"][-1]
    assert prompt.startswith("You answer one person's question using only their own captured")
    assert "Current datetime:" in prompt and "(Asia/Karachi)" in prompt
    assert "For status questions" in prompt
    assert f"[id {db_id}] " in prompt and "space: work · note" in prompt
    assert "SQLite with FTS5" in prompt
    assert f"[id {gym_id}]" not in prompt  # only FTS matches are sent
    assert "Question: what did I decide about sqlite vs postgres?" in prompt


def test_task_header_carries_status(ai_client, monkeypatch, tmp_path):
    set_classify_reply(
        monkeypatch,
        proposal(
            shape="task",
            text="ship the invoice",
            space="finance",
            title="Ship the invoice",
            due="2026-09-20",
        ),
    )
    item = capture(ai_client, "ship the invoice")["items"][0]
    ai_client.patch(f"/api/items/{item['id']}", json={"status": "done"})
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Done.", [item["id"]])
    ai_client.post("/api/ask", json={"question": "invoice status?"})
    prompt = records(record)[-1]["argv"][-1]
    assert f"[id {item['id']}] " in prompt
    assert "task: Ship the invoice · due 2026-09-20 · done" in prompt


def test_ask_falls_back_to_recent_in_space(ai_client, monkeypatch, tmp_path):
    ids = seed(
        ai_client,
        monkeypatch,
        [("work", "alpha note"), ("home", "beta note"), ("work", "gamma note")],
    )
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Nothing on that.", [])
    r = ai_client.post("/api/ask", json={"question": "zzzz unknown", "space": "Work"})
    assert r.status_code == 200
    assert r.json()["matched"] is False and r.json()["item_ids"] == []
    prompt = records(record)[-1]["argv"][-1]
    assert f"[id {ids[0]}]" in prompt and f"[id {ids[2]}]" in prompt
    assert f"[id {ids[1]}]" not in prompt  # other space excluded


def test_ask_is_read_only(ai_client, monkeypatch):
    ids = seed(ai_client, monkeypatch, [("work", "immutable thing")])
    before = ai_client.get(f"/api/items/{ids[0]}").json()
    set_ask_reply(monkeypatch, "x", ids)
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
    r = ai_client.post("/api/ask", json={"question": "anything", "space": "travel"})
    assert r.status_code == 200 and r.json()["matched"] is False and r.json()["items"] == []


def test_ask_errors(ai_client, monkeypatch, auth):
    seed(ai_client, monkeypatch, [("work", "something")])
    monkeypatch.setenv("FAKE_CODEX_EXIT", "2")
    r = ai_client.post("/api/ask", json={"question": "something"})
    assert r.status_code == 502 and "ask failed" in r.json()["detail"]
    monkeypatch.delenv("FAKE_CODEX_EXIT")
    assert ai_client.post("/api/ask", json={"question": "   "}).status_code == 422
    assert auth.post("/api/ask", json={"question": "x"}).status_code == 503  # AI off


def test_ask_reply_shape_is_strict_json(ai_client, monkeypatch):
    seed(ai_client, monkeypatch, [("work", "something")])
    monkeypatch.setenv("FAKE_CODEX_REPLY_ASK", json.dumps({"answer": "", "item_ids": ["x", 1.5]}))
    body = ai_client.post("/api/ask", json={"question": "something"}).json()
    assert body["answer"] == "No answer." and body["item_ids"] == []
