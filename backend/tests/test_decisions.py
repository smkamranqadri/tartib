"""Approve, reject, and edit. AI is disabled here, so every capture lands in Needs Attention."""

from tests.test_classify import wait_classified


def captured(auth, text="x"):
    item_id = auth.post("/api/capture", json={"text": text}).json()["id"]
    return wait_classified(auth, item_id)


def test_approve_with_overrides(auth):
    item = captured(auth, "pay rent friday")
    r = auth.post(
        f"/api/items/{item['id']}/approve",
        json={"shape": "task", "space": "Home", "title": "Pay rent", "due": "2026-09-19"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["stage"] == "filed"
    assert body["shape"] == "task"
    assert body["space"] == "home"
    assert body["title"] == "Pay rent"
    assert body["due"] == "2026-09-19"
    assert body["proposal_error"] is None
    assert body["raw_text"] == "pay rent friday"


def test_approve_without_body_files_as_is(auth):
    item = captured(auth)
    body = auth.post(f"/api/items/{item['id']}/approve").json()
    assert body["stage"] == "filed" and body["shape"] == "note" and body["space"] == "inbox"


def test_approve_applies_stored_proposal(auth, settings):
    import sqlite3

    item = captured(auth)
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


def test_reject_files_note_in_inbox(auth):
    item = captured(auth, "whatever")
    body = auth.post(f"/api/items/{item['id']}/reject").json()
    assert body["stage"] == "filed"
    assert body["shape"] == "note"
    assert body["space"] == "inbox"
    assert body["title"] is None
    assert body["raw_text"] == "whatever"


def test_decisions_require_attention_stage(auth):
    item = captured(auth)
    auth.post(f"/api/items/{item['id']}/reject")
    assert auth.post(f"/api/items/{item['id']}/approve").status_code == 409
    assert auth.post(f"/api/items/{item['id']}/reject").status_code == 409


def test_edit_fields(auth):
    item = captured(auth)
    auth.post(f"/api/items/{item['id']}/approve", json={"shape": "task", "title": "T"})
    body = auth.patch(
        f"/api/items/{item['id']}",
        json={"starred": True, "status": "done", "remind_at": "2026-09-18T09:00:00+05:00"},
    ).json()
    assert body["starred"] is True
    assert body["status"] == "done"
    assert body["remind_at"] == "2026-09-18T04:00:00Z"
    assert body["title"] == "T"
    # switching to note clears task fields
    body = auth.patch(f"/api/items/{item['id']}", json={"shape": "note"}).json()
    assert body["title"] is None and body["remind_at"] is None


def test_edit_cannot_touch_raw_text(auth):
    item = captured(auth)
    r = auth.patch(f"/api/items/{item['id']}", json={"raw_text": "nope"})
    assert r.status_code == 422
    r = auth.patch(f"/api/items/{item['id']}", json={"stage": "filed"})
    assert r.status_code == 422
