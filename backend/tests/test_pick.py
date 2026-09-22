"""Pick for me (slice 32): the AI stars up to three open tasks, and the next pick takes back only
the stars it set."""

from __future__ import annotations

import json
import sqlite3

from tests.conftest import records


def task(client, text, due=None, space="work"):
    body = {"shape": "task", "space": space, "text": text}
    if due:
        body["due"] = due
    r = client.post("/api/items", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def set_pick_reply(monkeypatch, *picks):
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY_PICK",
        json.dumps({"picks": [{"label": label, "reason": reason} for label, reason in picks]}),
    )


def today_ids(client):
    return {i["id"] for i in client.get("/api/today").json()["items"]}


def thoughts(client, item_id):
    return [t["body"] for t in client.get(f"/api/items/{item_id}/thoughts").json()["thoughts"]]


def calls(tmp_path, kind):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ai_calls WHERE kind = ?", (kind,)).fetchall()
    conn.close()
    return rows


def test_a_pick_stars_tasks_off_today_and_says_why(ai_client, monkeypatch, tmp_path):
    on_today = task(ai_client, "pay the electricity bill", due="2000-01-01")
    a = task(ai_client, "write the release notes")
    b = task(ai_client, "call the plumber")
    assert today_ids(ai_client) == {on_today["id"]}
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    # Candidates are dated first, then longest untouched: a is t1, b is t2.
    set_pick_reply(monkeypatch, ("t2", "It has waited  longest."), ("t1", "Quick win."))
    r = ai_client.post("/api/pick", json={"steer": "an hour, low energy"})
    assert r.status_code == 200, r.text
    got = r.json()["picks"]
    assert [p["item"]["id"] for p in got] == [b["id"], a["id"]]
    assert all(p["item"]["starred"] and p["item"]["picked_at"] for p in got)
    assert today_ids(ai_client) == {on_today["id"], a["id"], b["id"]}
    assert thoughts(ai_client, b["id"]) == ["Picked for today: It has waited longest."]
    prompt = records(record)[0]["argv"][-1]
    assert "an hour, low energy" in prompt
    shown, offered = prompt.split("\nCandidates (")
    assert "pay the electricity bill" in shown.split("Already on Today")[-1]
    assert "pay the electricity bill" not in offered
    [call] = calls(tmp_path, "pick")
    assert call["ok"] == 1 and call["candidates_n"] == 2


def test_a_second_pick_takes_back_only_its_own_stars(ai_client, monkeypatch, tmp_path):
    mine = task(ai_client, "renew passport")
    ai_client.patch(f"/api/items/{mine['id']}", json={"starred": True})
    first = task(ai_client, "tidy the garage")
    second = task(ai_client, "book dentist")
    set_pick_reply(monkeypatch, ("t1", "First."))
    [p] = ai_client.post("/api/pick", json={}).json()["picks"]
    assert p["item"]["id"] == first["id"]
    # The last pick's task is a candidate again, not something already on Today; the pick
    # touched it, so it now sorts after the untouched one.
    set_pick_reply(monkeypatch, ("t1", "Second."))
    [p] = ai_client.post("/api/pick", json={}).json()["picks"]
    assert p["item"]["id"] == second["id"]
    assert [c["candidates_n"] for c in calls(tmp_path, "pick")] == [2, 2]
    assert today_ids(ai_client) == {mine["id"], second["id"]}
    assert ai_client.get(f"/api/items/{mine['id']}").json()["starred"] is True


def test_a_star_touched_by_hand_is_kept(ai_client, monkeypatch):
    kept = task(ai_client, "tidy the garage")
    other = task(ai_client, "book dentist")
    set_pick_reply(monkeypatch, ("t1", "First."))
    ai_client.post("/api/pick", json={})
    ai_client.patch(f"/api/items/{kept['id']}", json={"starred": False})
    r = ai_client.patch(f"/api/items/{kept['id']}", json={"starred": True})
    assert r.json()["picked_at"] is None
    # kept is now on Today by its own star, so other is the only candidate.
    set_pick_reply(monkeypatch, ("t1", "Next."))
    [p] = ai_client.post("/api/pick", json={}).json()["picks"]
    assert p["item"]["id"] == other["id"]
    assert today_ids(ai_client) == {kept["id"], other["id"]}


def test_an_invented_label_changes_nothing(ai_client, monkeypatch, tmp_path):
    a = task(ai_client, "tidy the garage")
    set_pick_reply(monkeypatch, ("t1", "First."))
    ai_client.post("/api/pick", json={})
    set_pick_reply(monkeypatch, ("t9", "Not a candidate."))
    r = ai_client.post("/api/pick", json={})
    assert r.status_code == 502
    assert "named no task" in r.json()["detail"]
    assert today_ids(ai_client) == {a["id"]}  # the last pick stands
    assert thoughts(ai_client, a["id"]) == ["Picked for today: First."]
    assert [c["ok"] for c in calls(tmp_path, "pick")] == [1, 0]


def test_a_failed_call_changes_nothing_and_says_why(ai_client, monkeypatch, tmp_path):
    a = task(ai_client, "tidy the garage")
    set_pick_reply(monkeypatch, ("t1", "First."))
    ai_client.post("/api/pick", json={})
    monkeypatch.setenv("FAKE_CODEX_EXIT", "1")
    monkeypatch.setenv(
        "FAKE_CODEX_ERROR", "You've hit your usage limit. Try again at 11:46 AM."
    )
    r = ai_client.post("/api/pick", json={})
    assert r.status_code == 502
    assert "usage limit" in r.json()["detail"]
    assert today_ids(ai_client) == {a["id"]}
    assert calls(tmp_path, "pick")[-1]["reason"] == "usage_limit"


def test_nothing_to_pick_costs_no_call(ai_client, monkeypatch, tmp_path):
    task(ai_client, "due already", due="2000-01-01")
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    r = ai_client.post("/api/pick", json={})
    assert r.status_code == 200
    assert r.json()["picks"] == [] and r.json()["message"]
    assert not record.exists()


def test_pick_needs_ai(auth):
    assert auth.post("/api/pick", json={}).status_code == 503
