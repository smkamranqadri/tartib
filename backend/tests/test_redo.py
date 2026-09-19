"""Tell it why: disagreeing takes a reason and asks the classifier again (replaced Reject)."""

from __future__ import annotations

from tests.conftest import capture, proposal, records, set_classify_reply


def waiting(ai_client, monkeypatch, text="call Sara about the lease"):
    set_classify_reply(monkeypatch, proposal(shape="note", space="work", confidence=0.5))
    item = capture(ai_client, text)["items"][0]
    assert item["stage"] == "attention"
    return item


def redo(ai_client, item, reason):
    return ai_client.post(f"/api/items/{item['id']}/redo", json={"reason": reason})


def test_a_reason_is_sent_and_a_confident_answer_files_itself(ai_client, monkeypatch, tmp_path):
    item = waiting(ai_client, monkeypatch)
    record = tmp_path / "codex.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(
        monkeypatch, proposal(shape="task", space="home", title="Call Sara", confidence=0.95)
    )

    r = redo(ai_client, item, "  this is  a home task, not a work note ")
    assert r.status_code == 200, r.text
    body = r.json()
    assert (body["stage"], body["shape"], body["space"]) == ("filed", "task", "home")
    assert body["proposal"]["space"] == "home" and body["raw_text"] == item["raw_text"]
    assert body["feedback"].endswith(": this is a home task, not a work note")

    [call] = records(record)
    prompt = call["argv"][-1]
    assert "Their reason: this is a home task, not a work note" in prompt
    assert '"space":"work"' in prompt.replace(" ", "")  # the earlier proposal goes along
    assert prompt.rstrip().endswith(item["raw_text"])  # and the text is still last


def test_an_unsure_answer_keeps_it_waiting_with_the_new_proposal(ai_client, monkeypatch):
    item = waiting(ai_client, monkeypatch)
    set_classify_reply(monkeypatch, proposal(shape="task", space="home", title="T", confidence=0.4))
    body = redo(ai_client, item, "it is a task").json()
    assert body["stage"] == "attention" and body["shape"] == "task" and body["space"] == "home"
    assert body["proposal"]["confidence"] == 0.4


def test_the_space_policy_still_decides(ai_client, monkeypatch):
    ai_client.put("/api/spaces/home/policy", json={"policy": "ask"})
    item = waiting(ai_client, monkeypatch)
    set_classify_reply(monkeypatch, proposal(shape="task", space="home", confidence=0.99))
    assert redo(ai_client, item, "home").json()["stage"] == "attention"


def test_reasons_accumulate_and_survive_a_failed_try(ai_client, monkeypatch):
    item = waiting(ai_client, monkeypatch)
    set_classify_reply(monkeypatch, proposal(shape="note", space="work", confidence=0.5))
    redo(ai_client, item, "first reason")
    monkeypatch.setenv("FAKE_CODEX_EXIT", "3")
    r = redo(ai_client, item, "second reason")
    assert r.status_code == 502 and "Could not try again" in r.json()["detail"]
    after = ai_client.get(f"/api/items/{item['id']}").json()
    assert after["stage"] == "attention" and after["proposal"] is not None
    lines = after["feedback"].split("\n")
    assert [line.split(": ", 1)[1] for line in lines] == ["first reason", "second reason"]


def test_what_it_refuses(ai_client, auth, monkeypatch):
    item = waiting(ai_client, monkeypatch)
    assert redo(ai_client, item, "   ").status_code == 422
    ai_client.post(f"/api/items/{item['id']}/approve", json={"space": "work"})
    assert redo(ai_client, item, "too late").status_code == 409  # filed: nothing to disagree with
    off = capture(auth, "no classifier here")["items"][0]
    r = auth.post(f"/api/items/{off['id']}/redo", json={"reason": "try"})
    assert r.status_code == 409 and "off" in r.json()["detail"]


def test_reject_is_gone(auth):
    item = capture(auth, "x")["items"][0]
    assert auth.post(f"/api/items/{item['id']}/reject").status_code in (404, 405)
