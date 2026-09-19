"""Filing an item by hand from a space page: no classifier, and nothing ever sends it to one."""

from __future__ import annotations

import sqlite3

from tartib.reclassify import select_ids


def test_a_direct_task_is_filed_with_no_classifier_call(ai_client, tmp_path, monkeypatch):
    record = tmp_path / "codex.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    r = ai_client.post(
        "/api/items",
        json={
            "shape": "task",
            "space": "home",
            "text": "  Fix the gate latch  ",
            "due": "2026-09-25",
        },
    )
    assert r.status_code == 201, r.text
    item = r.json()
    assert (item["stage"], item["shape"], item["space"]) == ("filed", "task", "home")
    assert item["raw_text"] == "Fix the gate latch" and item["due"] == "2026-09-25"
    assert item["proposal"] is None and item["proposal_error"] is None
    assert not record.exists()  # the classifier never ran

    cap = ai_client.get(f"/api/captures/{item['capture_id']}").json()
    assert (
        cap["status"] == "done" and cap["direct"] == 1 and cap["raw_text"] == "Fix the gate latch"
    )


def test_a_note_carries_no_due_date(auth):
    r = auth.post(
        "/api/items", json={"shape": "note", "space": "work", "text": "x", "due": "2026-09-25"}
    )
    assert r.status_code == 201 and r.json()["due"] is None


def test_the_space_must_exist(auth):
    r = auth.post("/api/items", json={"shape": "note", "space": "nowhere", "text": "x"})
    assert r.status_code == 422
    assert auth.get("/api/recent").json()["captures"] == []  # no orphan capture left behind


def test_reclassify_never_picks_a_direct_capture(auth, settings):
    direct = auth.post("/api/items", json={"shape": "note", "space": "work", "text": "mine"}).json()
    conn = sqlite3.connect(settings.db_path)
    conn.row_factory = sqlite3.Row
    try:
        assert direct["capture_id"] not in select_ids(conn, "all")
        assert direct["capture_id"] not in select_ids(conn, "attention")
    finally:
        conn.close()
