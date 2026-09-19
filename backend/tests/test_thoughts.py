"""The thought section: an append-only log on an item, searched and read by Ask and the brief."""

from __future__ import annotations

import sqlite3

import pytest

from tests.conftest import capture, one_item, proposal, records, set_ask_reply, set_classify_reply


def think(client, item_id, body):
    r = client.post(f"/api/items/{item_id}/thoughts", json={"body": body})
    assert r.status_code == 201, r.text
    return r.json()


def test_entries_append_and_count(auth):
    item = one_item(auth, "renovate the kitchen")
    assert think(auth, item["id"], " first idea ")["thought_count"] == 1
    assert think(auth, item["id"], "second idea")["thought_count"] == 2
    got = auth.get(f"/api/items/{item['id']}/thoughts").json()["thoughts"]
    assert [t["body"] for t in got] == ["first idea", "second idea"]  # oldest first, trimmed
    assert auth.get(f"/api/items/{item['id']}").json()["thought_count"] == 2
    assert auth.post(f"/api/items/{item['id']}/thoughts", json={"body": "   "}).status_code == 422
    assert auth.post("/api/items/9999/thoughts", json={"body": "x"}).status_code == 404


def test_an_entry_cannot_be_rewritten(auth, settings):
    item = one_item(auth, "x")
    think(auth, item["id"], "as written")
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="append-only"):
        conn.execute("UPDATE item_thoughts SET body = 'changed'")
    conn.close()


def test_a_thought_does_not_make_an_open_editor_stale(auth):
    """Adding one is not an edit of the item, so updated_at stays and a save still lands."""
    item = one_item(auth, "stale check")
    loaded = auth.get(f"/api/items/{item['id']}").json()["updated_at"]
    think(auth, item["id"], "meanwhile")
    assert auth.get(f"/api/items/{item['id']}").json()["updated_at"] == loaded
    r = auth.patch(f"/api/items/{item['id']}", json={"title": "T", "expected_updated_at": loaded})
    assert r.status_code == 200


def test_search_finds_an_item_by_its_thoughts(auth):
    plain = one_item(auth, "fix the fence")
    other = one_item(auth, "zebra crossing")  # matched by its own text
    think(auth, plain["id"], "use galvanised zebra nails")
    ids = [i["id"] for i in auth.get("/api/items", params={"q": "zebra"}).json()["items"]]
    assert ids == [other["id"], plain["id"]]  # own-text match first, then by thought


def test_ask_retrieves_by_thought_and_reads_it(ai_client, monkeypatch, tmp_path):
    set_classify_reply(monkeypatch, proposal(space="home", confidence=0.95))
    item = capture(ai_client, "fix the fence")["items"][0]
    think(ai_client, item["id"], "the posts are rotten, need concrete")
    record = tmp_path / "ask.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Concrete.", [item["id"]])
    r = ai_client.post("/api/ask", json={"question": "what do the posts need?"})
    assert r.status_code == 200 and r.json()["item_ids"] == [item["id"]]
    prompt = records(record)[-1]["argv"][-1]
    assert "Thoughts:\n- " in prompt and "the posts are rotten, need concrete" in prompt


def test_the_brief_reads_thoughts_and_a_new_one_refreshes_it(ai_client, monkeypatch, tmp_path):
    set_classify_reply(monkeypatch, proposal(space="home", confidence=0.95))
    item = capture(ai_client, "fix the fence")["items"][0]
    record = tmp_path / "brief.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "A fence.", [item["id"]])
    ai_client.get("/api/spaces/home/brief")
    ai_client.get("/api/spaces/home/brief")  # cached: no new call
    assert len(records(record)) == 1
    think(ai_client, item["id"], "cedar, not pine")
    ai_client.get("/api/spaces/home/brief")
    calls = records(record)
    assert len(calls) == 2 and "cedar, not pine" in calls[-1]["argv"][-1]


def test_deleting_the_item_deletes_its_thoughts(auth, settings):
    item = one_item(auth, "gone soon")
    think(auth, item["id"], "a thought")
    auth.delete(f"/api/items/{item['id']}")
    conn = sqlite3.connect(settings.db_path)
    assert conn.execute("SELECT COUNT(*) FROM item_thoughts").fetchone()[0] == 0
    conn.close()
