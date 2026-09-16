import sqlite3

import pytest

from tests.conftest import PASSWORD, capture, wait_capture


def test_capture_is_stored_once_and_returns_immediately(auth):
    r = auth.post("/api/capture", json={"text": "  buy milk  "})
    assert r.status_code == 201
    cap = wait_capture(auth, r.json()["id"])
    assert cap["raw_text"] == "buy milk"
    assert cap["source"] == "api"
    assert cap["created_at"].endswith("Z")
    # AI off: one plain note waits for a human, the reason kept on both rows
    assert cap["status"] == "error" and cap["error"] == "AI not configured"
    assert len(cap["items"]) == 1
    item = cap["items"][0]
    assert item["capture_id"] == cap["id"]
    assert item["raw_text"] == "buy milk"
    assert item["stage"] == "attention" and item["shape"] == "note" and item["space"] is None
    assert item["proposal"] is None and item["proposal_error"] == "AI not configured"
    assert cap["answer"] is None


def test_source_is_web_for_cookie_sessions(client):
    client.post("/api/login", json={"password": PASSWORD})
    cap = capture(client, "from the app")
    assert cap["source"] == "web"


def test_capture_rejects_blank(auth):
    assert auth.post("/api/capture", json={"text": "   "}).status_code == 422
    assert auth.post("/api/capture", json={"text": ""}).status_code == 422


def test_missing_rows_404(auth):
    assert auth.get("/api/items/999").status_code == 404
    assert auth.get("/api/captures/999").status_code == 404


def test_raw_text_is_immutable_on_both_tables(auth, settings):
    cap = capture(auth, "original")
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE captures SET raw_text = 'changed' WHERE id = ?", (cap["id"],))
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE items SET raw_text = 'changed' WHERE id = ?", (cap["items"][0]["id"],))
    assert auth.get(f"/api/captures/{cap['id']}").json()["raw_text"] == "original"


def test_filed_items_must_have_a_space(settings, auth):
    cap = capture(auth, "x")
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE items SET stage = 'filed' WHERE id = ?", (cap["items"][0]["id"],))
