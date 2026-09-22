"""Approve and edit against configured spaces. Tell-it-why is in test_redo.py."""

import sqlite3

from tests.conftest import capture, one_item, proposal, set_classify_reply


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


def test_decisions_require_attention_stage(auth):
    item = one_item(auth, "x")
    auth.post(f"/api/items/{item['id']}/approve", json={"space": "work"})
    assert auth.post(f"/api/items/{item['id']}/approve").status_code == 409
    assert auth.post(f"/api/items/{item['id']}/redo", json={"reason": "no"}).status_code == 409


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


def test_a_stale_save_is_refused_and_a_fresh_one_taken(auth):
    """Two devices open one item; the second to save must not silently erase the first."""
    item = one_item(auth, "stale save")
    loaded = item["updated_at"]

    first = auth.patch(
        f"/api/items/{item['id']}", json={"title": "Phone", "expected_updated_at": loaded}
    )
    assert first.status_code == 200, first.text
    assert first.json()["updated_at"] != loaded

    stale = auth.patch(
        f"/api/items/{item['id']}", json={"title": "Desk", "expected_updated_at": loaded}
    )
    assert stale.status_code == 409
    assert "changed since you opened it" in stale.json()["detail"]
    assert auth.get(f"/api/items/{item['id']}").json()["title"] == "Phone"  # nothing written

    fresh = first.json()["updated_at"]
    again = auth.patch(
        f"/api/items/{item['id']}", json={"title": "Desk", "expected_updated_at": fresh}
    )
    assert again.status_code == 200 and again.json()["title"] == "Desk"


def test_a_toggle_without_a_timestamp_is_never_refused(auth):
    """Star and done come from rows that may be minutes old; a quick tick must just work."""
    item = one_item(auth, "toggle")
    auth.patch(f"/api/items/{item['id']}", json={"title": "changed elsewhere"})
    r = auth.patch(f"/api/items/{item['id']}", json={"starred": True})
    assert r.status_code == 200 and r.json()["starred"] is True


def test_approving_with_an_edited_text_keeps_the_edit(ai_client, monkeypatch):
    """`file_item` cleaned the fields, then handed the cleaned dict to `update_fields`, which
    cleaned them again -- and `raw_text` is not an editable field name, so the second pass threw
    the edit away. The endpoint answered 200 and discarded the write; PATCH did not."""
    set_classify_reply(
        monkeypatch, proposal(shape="note", text="origial typo here", space=None, confidence=0.4)
    )
    item = capture(ai_client, "origial typo here")["items"][0]
    assert item["stage"] == "attention"

    filed = ai_client.post(
        f"/api/items/{item['id']}/approve",
        json={"space": "work", "text": "original, typo fixed"},
    ).json()
    assert filed["stage"] == "filed"
    assert filed["raw_text"] == "original, typo fixed"
