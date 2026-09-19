"""Space summary, briefs with fingerprint caching, updated_at triggers, active space."""

import sqlite3
import time
from datetime import date, timedelta

from tests.conftest import capture, one_item, proposal, records, set_ask_reply, set_classify_reply


def file_note(client, monkeypatch, text, space):
    set_classify_reply(monkeypatch, proposal(shape="note", text=text, space=space))
    return capture(client, text)["items"][0]


def file_task(client, monkeypatch, text, space, due=None, conf=0.95):
    set_classify_reply(
        monkeypatch,
        proposal(shape="task", text=text, space=space, title=text, due=due, confidence=conf),
    )
    return capture(client, text)["items"][0]


def test_updated_at_is_kept_by_triggers(auth, settings):
    item = one_item(auth, "x")
    assert item["updated_at"] is not None
    conn = sqlite3.connect(settings.db_path)
    conn.execute("UPDATE items SET updated_at = '2020-01-01T00:00:00Z' WHERE id = ?", (item["id"],))
    conn.commit()
    conn.close()
    assert auth.get(f"/api/items/{item['id']}").json()["updated_at"] == "2020-01-01T00:00:00Z"
    auth.post(f"/api/items/{item['id']}/approve", json={"space": "work"})
    after = auth.get(f"/api/items/{item['id']}").json()["updated_at"]
    assert after > "2020-01-01T00:00:00Z"
    auth.patch(f"/api/items/{item['id']}", json={"starred": True})
    assert auth.get(f"/api/items/{item['id']}").json()["updated_at"] >= after


def test_spaces_summary_counts_and_order(ai_client, monkeypatch, settings):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    file_task(ai_client, monkeypatch, "late", "work", due=yesterday)
    file_task(ai_client, monkeypatch, "open", "work")
    done = file_task(ai_client, monkeypatch, "done", "work")
    ai_client.patch(f"/api/items/{done['id']}", json={"status": "done"})
    file_note(ai_client, monkeypatch, "a note", "work")
    file_note(ai_client, monkeypatch, "another", "home")
    one_item(ai_client, "parked")  # AI fallback: attention, space null... but AI is on here
    set_classify_reply(
        monkeypatch, proposal(shape="note", text="no space", space=None, confidence=0.3)
    )
    capture(ai_client, "no space")

    body = ai_client.get("/api/spaces/summary").json()
    names = [s["name"] for s in body["spaces"]]
    assert names[:2] == ["home", "work"] or names[:2] == ["work", "home"]
    assert set(names) == set(settings.spaces)
    work = next(s for s in body["spaces"] if s["name"] == "work")
    assert work == {**work, "open": 2, "notes": 1, "overdue": 1, "total": 4}
    assert work["last_activity"] is not None
    assert [s for s in body["spaces"] if s["name"] == "finance"][0]["last_activity"] is None
    # spaces with no activity come last
    assert names[2:] == ["health", "finance", "ideas", "travel"]  # no activity: config order
    assert body["unfiled"]["unfiled"] is True and body["unfiled"]["total"] >= 1


def test_a_session_in_the_space_regenerates_the_brief(ai_client, monkeypatch, tmp_path):
    """A pomodoro is the one thing besides an item that changes what the brief should say."""
    record = tmp_path / "calls.jsonl"
    task = file_task(ai_client, monkeypatch, "pray fajr", "health")
    file_task(ai_client, monkeypatch, "call the bank", "work")
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Open: pray fajr.", [task["id"]])

    assert ai_client.get("/api/spaces/health/brief").json()["fresh"] is True
    calls = len(records(record))
    assert ai_client.get("/api/spaces/health/brief").json()["fresh"] is False  # cached

    # a session on a task in another space leaves this brief alone
    other = ai_client.get("/api/items?space=work").json()["items"][0]
    elsewhere = ai_client.post("/api/sessions", json={"item_id": other["id"]}).json()
    ai_client.post(f"/api/sessions/{elsewhere['id']}/outcome", json={"outcome": "unfinished"})
    assert ai_client.get("/api/spaces/health/brief").json()["fresh"] is False
    assert len(records(record)) == calls

    # a session on a task in this space does not
    session = ai_client.post("/api/sessions", json={"item_id": task["id"]}).json()
    ai_client.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "unfinished"})
    set_ask_reply(monkeypatch, "Open: pray fajr. One session today.", [task["id"]])
    again = ai_client.get("/api/spaces/health/brief").json()
    assert again["fresh"] is True
    assert len(records(record)) == calls + 1
    # and the count reached the prompt as a fact, not an instruction
    prompt = records(record)[-1]["argv"][-1]
    assert "Today the user spent 1 pomodoro session on this space." in prompt


def test_a_session_with_no_task_touches_no_brief(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    task = file_task(ai_client, monkeypatch, "pray fajr", "health")
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Open: pray fajr.", [task["id"]])
    ai_client.get("/api/spaces/health/brief")
    calls = len(records(record))

    bare = ai_client.post("/api/sessions", json={}).json()
    ai_client.post(f"/api/sessions/{bare['id']}/outcome", json={"outcome": "done"})

    assert ai_client.get("/api/spaces/health/brief").json()["fresh"] is False
    assert len(records(record)) == calls


def test_brief_is_cached_by_fingerprint(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    file_task(ai_client, monkeypatch, "pray fajr", "health")
    file_note(ai_client, monkeypatch, "decided: gym at 7", "health")
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Open: pray fajr. Noted: gym at 7.", [1, 2])

    first = ai_client.get("/api/spaces/health/brief").json()
    assert first["fresh"] is True
    assert first["text"] == "Open: pray fajr. Noted: gym at 7."
    assert [i["raw_text"] for i in first["items"]] == ["pray fajr", "decided: gym at 7"]
    prompt = records(record)[-1]["argv"][-1]
    assert "Summarise the current state of this space" in prompt and "Max 5 lines" in prompt
    assert "[id 1] " in prompt and "[id 2] " in prompt
    calls = len(records(record))

    again = ai_client.get("/api/spaces/health/brief").json()
    assert again["fresh"] is False and again["text"] == first["text"]
    assert len(records(record)) == calls  # served from cache

    # a done tick does not invalidate the cache; a new item in the space does
    ai_client.patch("/api/items/1", json={"status": "done"})
    assert ai_client.get("/api/spaces/health/brief").json()["fresh"] is False
    assert len(records(record)) == calls
    set_ask_reply(monkeypatch, "Nothing open.", [2])
    file_note(ai_client, monkeypatch, "another health note", "health")
    calls = len(records(record))  # the classify call
    third = ai_client.get("/api/spaces/health/brief").json()
    assert third["fresh"] is True and third["text"] == "Nothing open."
    assert len(records(record)) == calls + 1

    # explicit refresh regenerates without a change
    forced = ai_client.get("/api/spaces/health/brief", params={"refresh": "true"}).json()
    assert forced["fresh"] is True and len(records(record)) == calls + 2


def test_brief_feeds_open_tasks_and_recent_notes_only(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    open_t = file_task(ai_client, monkeypatch, "open task", "work")
    done_t = file_task(ai_client, monkeypatch, "done task", "work")
    ai_client.patch(f"/api/items/{done_t['id']}", json={"status": "done"})
    note = file_note(ai_client, monkeypatch, "a note", "work")
    other = file_note(ai_client, monkeypatch, "elsewhere", "home")
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "ok", [])
    ai_client.get("/api/spaces/work/brief")
    prompt = records(record)[-1]["argv"][-1]
    assert f"[id {open_t['id']}] " in prompt and f"[id {note['id']}] " in prompt
    assert f"[id {done_t['id']}] " not in prompt and f"[id {other['id']}] " not in prompt


def test_brief_empty_space_and_unknown_space(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    body = ai_client.get("/api/spaces/travel/brief").json()
    assert body["text"] == "Nothing here yet." and body["items"] == [] and body["fresh"] is True
    assert not record.exists()  # no Codex call
    assert ai_client.get("/api/spaces/garage/brief").status_code == 404
    assert ai_client.get("/api/spaces/Travel/brief").status_code == 200


def test_brief_errors(ai_client, monkeypatch, auth):
    file_note(ai_client, monkeypatch, "x", "work")
    monkeypatch.setenv("FAKE_CODEX_EXIT", "2")
    r = ai_client.get("/api/spaces/work/brief")
    assert r.status_code == 502 and "brief failed" in r.json()["detail"]
    # AI off with items present
    item = one_item(auth, "y")
    auth.post(f"/api/items/{item['id']}/approve", json={"space": "work"})
    assert auth.get("/api/spaces/work/brief").status_code == 503


def test_today_reports_active_space(ai_client, monkeypatch):
    assert ai_client.get("/api/today").json()["active_space"] is None
    file_note(ai_client, monkeypatch, "a", "work")
    time.sleep(0.05)
    b = file_note(ai_client, monkeypatch, "b", "home")
    assert ai_client.get("/api/today").json()["active_space"] == "home"
    time.sleep(0.05)
    ai_client.patch(f"/api/items/{b['id'] - 1}", json={"starred": True})
    assert ai_client.get("/api/today").json()["active_space"] == "work"


def test_migration_0003_backfills_updated_at(tmp_path):
    from tartib import db
    from tests.test_migration import build_v1

    path = str(tmp_path / "v1.db")
    build_v1(path)
    conn = db.connect(path)
    assert db.migrate(conn) == 13
    rows = conn.execute("SELECT id, updated_at, created_at FROM items").fetchall()
    assert rows and all(r["updated_at"] == r["created_at"] for r in rows)
    assert conn.execute("SELECT COUNT(*) FROM briefs").fetchone()[0] == 0
    conn.close()
