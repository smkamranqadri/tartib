"""Approve, reject, and edit against configured spaces."""

import sqlite3

from tests.conftest import one_item


def test_approve_requires_a_space(auth):
    item = one_item(auth, "pay rent friday")
    r = auth.post(f"/api/items/{item['id']}/approve")
    assert r.status_code == 422 and "space" in r.json()["detail"]
    r = auth.post(f"/api/items/{item['id']}/approve", json={"space": "garage"})
    assert r.status_code == 422 and "unknown space" in r.json()["detail"]
    r = auth.post(
        f"/api/items/{item['id']}/approve",
        json={"shape": "task", "space": "Home", "title": "Pay rent", "due": "2026-09-19"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "filed" and body["shape"] == "task" and body["space"] == "home"
    assert body["title"] == "Pay rent" and body["due"] == "2026-09-19"
    assert body["raw_text"] == "pay rent friday"


def test_approve_applies_stored_proposal(auth, settings):
    item = one_item(auth, "x")
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        "UPDATE items SET proposal_json = ? WHERE id = ?",
        ('{"shape":"task","space":"work","title":"Ship it","confidence":0.5}', item["id"]),
    )
    conn.commit()
    conn.close()
    body = auth.post(f"/api/items/{item['id']}/approve", json={"starred": True}).json()
    assert body["shape"] == "task" and body["space"] == "work" and body["title"] == "Ship it"
    assert body["starred"] is True
    assert body["proposal"]["confidence"] == 0.5  # kept for inspection


def test_reject_discards_proposal_and_keeps_item_waiting(auth, settings):
    item = one_item(auth, "whatever")
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        "UPDATE items SET shape='task', title='T', due='2026-01-01',"
        ' proposal_json=\'{"shape":"task"}\' WHERE id = ?',
        (item["id"],),
    )
    conn.commit()
    conn.close()
    body = auth.post(f"/api/items/{item['id']}/reject").json()
    assert body["stage"] == "attention"
    assert body["shape"] == "note" and body["space"] is None
    assert body["title"] is None and body["due"] is None
    assert body["proposal"] is None and body["proposal_error"] is None
    assert body["raw_text"] == "whatever"
    assert [i["id"] for i in auth.get("/api/attention").json()["items"]] == [item["id"]]


def test_decisions_require_attention_stage(auth):
    item = one_item(auth, "x")
    auth.post(f"/api/items/{item['id']}/approve", json={"space": "work"})
    assert auth.post(f"/api/items/{item['id']}/approve").status_code == 409
    assert auth.post(f"/api/items/{item['id']}/reject").status_code == 409


def test_edit_fields_and_space_validation(auth):
    item = one_item(auth, "x")
    auth.post(
        f"/api/items/{item['id']}/approve", json={"shape": "task", "space": "work", "title": "T"}
    )
    body = auth.patch(
        f"/api/items/{item['id']}",
        json={"starred": True, "status": "done", "remind_at": "2026-09-18T09:00:00+05:00"},
    ).json()
    assert body["starred"] is True and body["status"] == "done"
    assert body["remind_at"] == "2026-09-18T04:00:00Z" and body["title"] == "T"
    body = auth.patch(f"/api/items/{item['id']}", json={"shape": "note"}).json()
    assert body["title"] is None and body["remind_at"] is None
    assert auth.patch(f"/api/items/{item['id']}", json={"space": "garage"}).status_code == 422
    r = auth.patch(f"/api/items/{item['id']}", json={"space": None})
    assert r.status_code == 422 and "space" in r.json()["detail"]
    assert (
        auth.patch(f"/api/items/{item['id']}", json={"space": "Travel"}).json()["space"] == "travel"
    )


def test_edit_cannot_touch_raw_text_or_stage(auth):
    item = one_item(auth, "x")
    assert auth.patch(f"/api/items/{item['id']}", json={"raw_text": "nope"}).status_code == 422
    assert auth.patch(f"/api/items/{item['id']}", json={"stage": "filed"}).status_code == 422
    assert auth.patch(f"/api/items/{item['id']}", json={"capture_id": 5}).status_code == 422
    assert auth.patch(f"/api/items/{item['id']}", json={"raw_text": "nope"}).status_code == 422
