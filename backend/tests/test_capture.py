import sqlite3

import pytest


def test_capture_lands_in_inbox(auth):
    r = auth.post("/api/capture", json={"text": "  buy milk  "})
    assert r.status_code == 201
    item = auth.get(f"/api/items/{r.json()['id']}").json()
    assert item["raw_text"] == "buy milk"
    assert item["stage"] == "inbox"
    assert item["shape"] == "note"
    assert item["space"] == "inbox"
    assert item["proposal"] is None
    assert item["created_at"].endswith("Z")


def test_capture_rejects_blank(auth):
    assert auth.post("/api/capture", json={"text": "   "}).status_code == 422
    assert auth.post("/api/capture", json={"text": ""}).status_code == 422


def test_missing_item_404(auth):
    assert auth.get("/api/items/999").status_code == 404


def test_raw_text_is_immutable(auth, settings):
    item_id = auth.post("/api/capture", json={"text": "original"}).json()["id"]
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE items SET raw_text = 'changed' WHERE id = ?", (item_id,))
    assert auth.get(f"/api/items/{item_id}").json()["raw_text"] == "original"
