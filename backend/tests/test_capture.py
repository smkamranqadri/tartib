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


def test_capture_text_is_immutable_item_text_is_yours(auth, settings):
    cap = capture(auth, "original")
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="immutable"):
        conn.execute("UPDATE captures SET raw_text = 'changed' WHERE id = ?", (cap["id"],))
    conn.close()
    item_id = cap["items"][0]["id"]
    body = auth.patch(f"/api/items/{item_id}", json={"text": "  edited by me  "}).json()
    assert body["raw_text"] == "edited by me"
    assert auth.get(f"/api/captures/{cap['id']}").json()["raw_text"] == "original"
    assert [i["id"] for i in auth.get("/api/items", params={"q": "edited"}).json()["items"]] == [
        item_id
    ]
    assert auth.get("/api/items", params={"q": "original"}).json()["items"] == []
    assert (
        auth.patch(f"/api/items/{item_id}", json={"text": "   "}).json()["raw_text"]
        == "edited by me"
    )


def test_delete_item_keeps_capture(auth):
    cap = capture(auth, "keep me")
    item_id = cap["items"][0]["id"]
    assert auth.delete(f"/api/items/{item_id}").json() == {"ok": True, "id": item_id}
    assert auth.get(f"/api/items/{item_id}").status_code == 404
    assert auth.delete(f"/api/items/{item_id}").status_code == 404
    assert auth.get(f"/api/captures/{cap['id']}").json()["raw_text"] == "keep me"
    assert auth.get(f"/api/captures/{cap['id']}").json()["items"] == []
    assert auth.get("/api/items", params={"q": "keep"}).json()["items"] == []


def test_filed_items_must_have_a_space(settings, auth):
    cap = capture(auth, "x")
    conn = sqlite3.connect(settings.db_path)
    with pytest.raises(sqlite3.IntegrityError, match="CHECK"):
        conn.execute("UPDATE items SET stage = 'filed' WHERE id = ?", (cap["items"][0]["id"],))


def test_a_queued_capture_is_safe_to_send_twice(auth):
    """The point of client_id: a send that stored the row but whose response was lost is
    retried, and the retry finds the capture instead of making a second one."""
    body = {"text": "call the dentist", "client_id": "b4f1c2d3-e5a6-4789-9abc-def012345678"}
    first = auth.post("/api/capture", json=body)
    assert first.status_code == 201

    again = auth.post("/api/capture", json=body)
    assert again.status_code == 200, "a repeat is not a new capture"
    assert again.json()["id"] == first.json()["id"]

    # And there is genuinely one row, not two that merely share an id in the response.
    # (Today's list, not /api/recent: with AI off this capture waits in Needs Attention, which
    # the Recent page leaves out.)
    recent = auth.get("/api/today").json()["recent"]
    assert [c["raw_text"] for c in recent].count("call the dentist") == 1


def test_the_retry_wins_even_when_the_text_differs(auth):
    """The id identifies the capture, not the request. A client that edited the text before
    retrying still gets the one that was stored -- raw_text is immutable by rule 1, so the
    alternative would be either a lie or a second capture."""
    first = auth.post("/api/capture", json={"text": "original", "client_id": "same-id-here-01"})
    again = auth.post("/api/capture", json={"text": "edited", "client_id": "same-id-here-01"})
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert wait_capture(auth, first.json()["id"])["raw_text"] == "original"


def test_captures_without_a_client_id_are_never_deduplicated(auth):
    """curl, the Shortcut, and every capture made before this column existed send none. Two of
    them with the same text are two captures, because that is what the user did."""
    a = auth.post("/api/capture", json={"text": "same words"})
    b = auth.post("/api/capture", json={"text": "same words"})
    assert a.status_code == 201 and b.status_code == 201
    assert a.json()["id"] != b.json()["id"]


def test_a_client_id_has_to_be_plausible(auth):
    assert auth.post("/api/capture", json={"text": "x", "client_id": "short"}).status_code == 422
    assert auth.post("/api/capture", json={"text": "x", "client_id": "z" * 65}).status_code == 422


def test_two_sends_at_once_still_make_one_capture(auth, settings):
    """The lookup and the insert are not one statement, so two requests can both find nothing.
    The unique index is what actually decides it; this drives that path by inserting the row
    underneath the request, between its check and its write."""
    import sqlite3 as sq

    from tartib import items as items_module

    body = {"text": "raced", "client_id": "raced-client-id-0001"}
    real = items_module.capture_by_client_id
    state = {"planted": None}

    def plant_then_lookup(conn, client_id):
        found = real(conn, client_id)
        if found is None and state["planted"] is None:
            # Another request, arriving in the gap, gets there first.
            other = sq.connect(settings.db_path)
            other.execute(
                "INSERT INTO captures (raw_text, source, created_at, client_id)"
                " VALUES (?, 'web', '2026-09-18T00:00:00Z', ?)",
                ("raced", client_id),
            )
            other.commit()
            state["planted"] = int(
                other.execute("SELECT id FROM captures WHERE client_id = ?", (client_id,))
                .fetchone()[0]
            )
            other.close()
        return found

    items_module.capture_by_client_id = plant_then_lookup
    try:
        r = auth.post("/api/capture", json=body)
    finally:
        items_module.capture_by_client_id = real

    assert r.status_code == 200, "the loser of the race returns the winner's capture"
    assert r.json()["id"] == state["planted"]
