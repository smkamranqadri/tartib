"""Slice 30: a capture that splits waits for the owner, and can be kept as one."""

import pytest

from tests.conftest import capture, proposal, set_ask_reply, set_classify_reply

TEXT = "Page polish\n- smooth scrolling\n- hover effects on links"


def split(ai_client, monkeypatch, *spaces, text=TEXT):
    """A capture the fake classifier splits into one confident note per space given."""
    set_classify_reply(
        monkeypatch,
        *(proposal(text=f"piece {n}", space=s, confidence=0.99) for n, s in enumerate(spaces)),
    )
    return capture(ai_client, text)


def attention(ai_client):
    return ai_client.get("/api/attention").json()["items"]


def test_a_split_files_nothing_whatever_the_confidence_and_policy(ai_client, monkeypatch):
    ai_client.put("/api/spaces/work/policy", json={"policy": "file"})
    cap = split(ai_client, monkeypatch, "work", "work", "home")
    assert [i["stage"] for i in cap["items"]] == ["attention"] * 3
    assert [i["wait_reason"] for i in cap["items"]] == ["split"] * 3
    # The proposal is kept: approving a piece files it where the classifier said.
    assert [i["space"] for i in cap["items"]] == ["work", "work", "home"]


def test_one_proposal_files_as_before(ai_client, monkeypatch):
    [item] = split(ai_client, monkeypatch, "work")["items"]
    assert (item["stage"], item["wait_reason"]) == ("filed", None)


def test_one_item_and_a_question_is_not_a_split(ai_client, monkeypatch):
    set_classify_reply(
        monkeypatch,
        proposal(shape="task", text="buy milk", space="home", title="Buy milk"),
        proposal(shape="question", text="where did I park?"),
    )
    set_ask_reply(monkeypatch, "No idea.", [])
    [item] = capture(ai_client, "buy milk. where did I park?")["items"]
    assert item["stage"] == "filed"


def test_attention_says_how_many_pieces_and_whether_they_can_be_kept(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "work", "home")
    items = attention(ai_client)
    assert [i["split"] for i in items] == [{"of": 2, "whole": True}] * 2
    ai_client.post(f"/api/items/{cap['items'][0]['id']}/approve")
    [left] = attention(ai_client)
    assert left["split"] == {"of": 2, "whole": False}


def test_keep_as_one_puts_the_whole_text_back_as_one_waiting_note(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "ideas", "ideas", "ideas")
    r = ai_client.post(f"/api/captures/{cap['id']}/whole")
    assert r.status_code == 200, r.text
    note = r.json()
    assert note["raw_text"] == TEXT  # byte for byte, heading included
    assert (note["shape"], note["stage"], note["wait_reason"]) == ("note", "attention", "whole")
    # The pieces agreed, so their space is proposed and no question is asked.
    assert note["space"] == "ideas" and note["proposal"]["clarify"] is None
    assert [i["id"] for i in attention(ai_client)] == [note["id"]]
    assert [i["id"] for i in ai_client.get(f"/api/captures/{cap['id']}").json()["items"]] == [
        note["id"]
    ]
    filed = ai_client.post(f"/api/items/{note['id']}/approve").json()
    assert (filed["stage"], filed["space"], filed["raw_text"]) == ("filed", "ideas", TEXT)


def test_pieces_that_disagree_make_it_ask_where(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "work", "home", "work")
    note = ai_client.post(f"/api/captures/{cap['id']}/whole").json()
    assert note["space"] is None
    clarify = note["proposal"]["clarify"]
    assert clarify["field"] == "space"
    assert [o["value"] for o in clarify["options"]] == ["work", "home"]


@pytest.mark.parametrize("touch", ["approve", "edit", "thought", "session"])
def test_keep_as_one_is_refused_once_a_piece_is_started_on(ai_client, monkeypatch, touch):
    cap = split(ai_client, monkeypatch, "work", "home")
    piece = cap["items"][1]["id"]
    if touch == "approve":
        done = ai_client.post(f"/api/items/{piece}/approve")
    elif touch == "edit":
        done = ai_client.patch(f"/api/items/{piece}", json={"space": "work"})
    elif touch == "thought":
        done = ai_client.post(f"/api/items/{piece}/thoughts", json={"body": "hm"})
    else:
        done = ai_client.post("/api/sessions", json={"item_id": piece})
    assert done.status_code < 300, done.text
    r = ai_client.post(f"/api/captures/{cap['id']}/whole")
    assert r.status_code == 409
    assert len(ai_client.get(f"/api/captures/{cap['id']}").json()["items"]) == 2


def test_a_deleted_piece_does_not_block_it(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "work", "work", "work")
    ai_client.delete(f"/api/items/{cap['items'][0]['id']}")
    note = ai_client.post(f"/api/captures/{cap['id']}/whole").json()
    assert note["raw_text"] == TEXT


def test_keep_as_one_is_refused_for_a_capture_that_did_not_split(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "work")
    assert ai_client.post(f"/api/captures/{cap['id']}/whole").status_code == 409
    assert ai_client.post("/api/captures/9999/whole").status_code == 404


def test_keeping_it_twice_is_refused(ai_client, monkeypatch):
    cap = split(ai_client, monkeypatch, "work", "home")
    assert ai_client.post(f"/api/captures/{cap['id']}/whole").status_code == 200
    assert ai_client.post(f"/api/captures/{cap['id']}/whole").status_code == 409
