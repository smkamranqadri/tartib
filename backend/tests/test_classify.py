"""Classify adapter and background runner, with the AI endpoint mocked by respx."""

import json
import sqlite3
import time

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from tartib import db
from tartib.main import create_app
from tests.conftest import PASSWORD, make_settings

AI_URL = "http://ai.test/v1"
AI_ENV = {
    "TARTIB_AI_BASE_URL": AI_URL,
    "TARTIB_AI_MODEL": "test-model",
    "TARTIB_TZ": "Asia/Karachi",
}


def ai_reply(**fields):
    body = {"choices": [{"message": {"content": json.dumps(fields)}}]}
    return httpx.Response(200, json=body)


def wait_classified(client: TestClient, item_id: int, timeout: float = 3.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = client.get(f"/api/items/{item_id}").json()
        if item["stage"] != "inbox":
            return item
        time.sleep(0.02)
    raise AssertionError(f"item {item_id} never left inbox")


@pytest.fixture
def ai_client(tmp_path):
    with respx.mock(assert_all_called=False) as mock:
        with TestClient(create_app(make_settings(tmp_path, **AI_ENV))) as client:
            client.headers["Authorization"] = f"Bearer {PASSWORD}"
            client.mock = mock
            yield client


def test_confident_proposal_is_filed(ai_client):
    route = ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(
            shape="task",
            space="Health ",
            title="Call the dentist",
            due="2026-09-18",
            remind_at="2026-09-18T09:00:00",
            confidence=0.95,
        )
    )
    r = ai_client.post("/api/capture", json={"text": "call the dentist tomorrow"})
    item_id = r.json()["id"]
    item = wait_classified(ai_client, item_id)
    assert item["stage"] == "filed"
    assert item["shape"] == "task"
    assert item["space"] == "health"
    assert item["title"] == "Call the dentist"
    assert item["due"] == "2026-09-18"
    # naive 09:00 in Asia/Karachi (UTC+5) is stored as 04:00Z
    assert item["remind_at"] == "2026-09-18T04:00:00Z"
    assert item["proposal"]["confidence"] == 0.95
    assert item["raw_text"] == "call the dentist tomorrow"
    sent = json.loads(route.calls.last.request.content)
    assert sent["model"] == "test-model"
    assert sent["response_format"] == {"type": "json_object"}
    assert "call the dentist tomorrow" in sent["messages"][1]["content"]


def test_unsure_proposal_needs_attention(ai_client):
    ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(shape="note", space="ideas", confidence=0.4)
    )
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


def test_note_proposal_drops_task_fields(ai_client):
    ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(
            shape="note", space="log", title="junk", due="2026-01-01", confidence=0.99
        )
    )
    item_id = ai_client.post("/api/capture", json={"text": "rain today"}).json()["id"]
    item = wait_classified(ai_client, item_id)
    assert item["stage"] == "filed"
    assert item["shape"] == "note"
    assert item["title"] is None and item["due"] is None


@pytest.mark.parametrize(
    "response, error_fragment",
    [
        (httpx.Response(500, text="boom"), "endpoint error"),
        (httpx.Response(200, json={"choices": [{"message": {"content": "not json"}}]}), "unusable"),
        (ai_reply(shape="task", confidence=1.7), "invalid proposal"),
        (ai_reply(shape="task"), "invalid proposal"),
    ],
)
def test_bad_endpoint_goes_to_attention(ai_client, response, error_fragment):
    ai_client.mock.post(f"{AI_URL}/chat/completions").mock(return_value=response)
    item_id = ai_client.post("/api/capture", json={"text": "x"}).json()["id"]
    item = wait_classified(ai_client, item_id)
    assert item["stage"] == "attention"
    assert item["proposal"] is None
    assert error_fragment in item["proposal_error"]


def test_ai_disabled_goes_to_attention(auth):
    item_id = auth.post("/api/capture", json={"text": "x"}).json()["id"]
    item = wait_classified(auth, item_id)
    assert item["stage"] == "attention"
    assert item["proposal_error"] == "AI not configured"


def test_startup_requeues_inbox_items(tmp_path):
    settings = make_settings(tmp_path, **AI_ENV)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    conn.execute(
        "INSERT INTO items (raw_text, created_at) VALUES ('left over', '2026-09-17T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    with respx.mock() as mock:
        mock.post(f"{AI_URL}/chat/completions").mock(
            return_value=ai_reply(shape="task", space="home", title="Left over", confidence=0.9)
        )
        with TestClient(create_app(settings)) as client:
            client.headers["Authorization"] = f"Bearer {PASSWORD}"
            item = wait_classified(client, 1)
    assert item["stage"] == "filed"
    assert item["title"] == "Left over"


def test_existing_spaces_are_sent_as_context(ai_client):
    route = ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(shape="note", space="work", confidence=0.9)
    )
    first = ai_client.post("/api/capture", json={"text": "one"}).json()["id"]
    wait_classified(ai_client, first)
    second = ai_client.post("/api/capture", json={"text": "two"}).json()["id"]
    wait_classified(ai_client, second)
    prompt = json.loads(route.calls.last.request.content)["messages"][1]["content"]
    assert "Existing spaces: work" in prompt
    assert "Asia/Karachi" in prompt


def test_crash_in_one_item_does_not_stop_the_runner(ai_client, settings):
    ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(shape="note", space="a", confidence=0.9)
    )
    ok = ai_client.post("/api/capture", json={"text": "fine"}).json()["id"]
    assert wait_classified(ai_client, ok)["stage"] == "filed"
    # a proposal_json that the store cannot apply: shape check constraint
    conn = sqlite3.connect(ai_client.app.state.settings.db_path)
    conn.execute(
        "INSERT INTO items (raw_text, created_at) VALUES ('poison', '2026-09-17T00:00:00Z')"
    )
    conn.commit()
    conn.close()
    poison = ai_client.get("/api/items/2").json()["id"]
    ai_client.mock.post(f"{AI_URL}/chat/completions").mock(
        return_value=ai_reply(shape="task", space="x" * 500, confidence=0.9)
    )
    ai_client.app.state.runner.enqueue(poison)
    wait_classified(ai_client, poison)
    after = ai_client.post("/api/capture", json={"text": "still alive"}).json()["id"]
    assert wait_classified(ai_client, after)["stage"] == "filed"
