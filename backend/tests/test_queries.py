"""Today (tasks + recent captures), Needs Attention, All, spaces."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from tartib.queries import fts_query
from tests.conftest import SPACES, capture, one_item, proposal, set_classify_reply


def add(auth, text, **fields):
    item = one_item(auth, text)
    fields.setdefault("space", "work")
    auth.post(f"/api/items/{item['id']}/approve", json=fields)
    return item["id"]


def ids(payload, key="items"):
    return [i["id"] for i in payload[key]]


def test_today_rules(auth, settings):
    today = datetime.now(UTC).astimezone(settings.zone).date()
    yesterday = (today - timedelta(days=1)).isoformat()
    tomorrow = (today + timedelta(days=1)).isoformat()
    past = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()

    due_today = add(auth, "a", shape="task", title="a", due=today.isoformat())
    overdue = add(auth, "b", shape="task", title="b", due=yesterday)
    later = add(auth, "c", shape="task", title="c", due=tomorrow)
    starred = add(auth, "d", shape="task", title="d", starred=True)
    reminded = add(auth, "e", shape="task", title="e", remind_at=past)
    reminder_later = add(auth, "f", shape="task", title="f", remind_at=future)
    plain_task = add(auth, "g", shape="task", title="g")
    note = add(auth, "h", shape="note")
    done = add(auth, "i", shape="task", title="i", due=today.isoformat(), status="done")
    pending = one_item(auth, "j")["id"]  # stays in attention

    payload = auth.get("/api/today").json()
    assert payload["date"] == today.isoformat()
    got = set(ids(payload))
    assert got == {due_today, overdue, starred, reminded}
    for absent in (later, reminder_later, plain_task, note, done, pending):
        assert absent not in got
    assert ids(payload)[:2] == [overdue, due_today]  # overdue first


def test_today_recent_is_newest_three_and_recent_page_is_fifty(auth):
    made = [capture(auth, f"note {i}") for i in range(12)]
    caps = [c["id"] for c in made]
    recent = auth.get("/api/today").json()["recent"]
    for c in made:  # file them: the page leaves out what is waiting in Needs Attention
        auth.post(f"/api/items/{c['items'][0]['id']}/approve", json={"space": "work"})
    assert [c["id"] for c in recent] == list(reversed(caps))[:3]
    page = auth.get("/api/recent").json()
    assert [c["id"] for c in page["captures"]] == list(reversed(caps)) and page[
        "next_before"
    ] is None
    first = auth.get("/api/recent", params={"limit": 5}).json()
    assert [c["id"] for c in first["captures"]] == list(reversed(caps))[:5]
    assert first["next_before"] == list(reversed(caps))[4]
    second = auth.get("/api/recent", params={"limit": 5, "before": first["next_before"]}).json()
    assert [c["id"] for c in second["captures"]] == list(reversed(caps))[5:10]
    third = auth.get("/api/recent", params={"limit": 5, "before": second["next_before"]}).json()
    assert [c["id"] for c in third["captures"]] == list(reversed(caps))[10:] and third[
        "next_before"
    ] is None
    assert recent[0]["raw_text"] == "note 11"
    assert recent[0]["status"] == "error" and len(recent[0]["items"]) == 1
    assert recent[0]["items"][0]["stage"] == "attention"


def test_recent_page_leaves_out_what_is_waiting(ai_client, monkeypatch):
    """Needs Attention sits above Recent in the Inbox; the same item should not be in both."""
    set_classify_reply(monkeypatch, proposal(space="work"), proposal(confidence=0.3))
    mixed = capture(ai_client, "one filed, one unsure")
    # A split files nothing itself (slice 30), so one piece is filed by hand.
    first, waiting = mixed["items"]
    filed = ai_client.post(f"/api/items/{first['id']}/approve").json()
    assert (filed["stage"], waiting["stage"]) == ("filed", "attention")
    set_classify_reply(monkeypatch, proposal(confidence=0.3))
    parked = capture(ai_client, "only unsure")

    page = ai_client.get("/api/recent").json()["captures"]
    assert [c["id"] for c in page] == [mixed["id"]]
    assert [i["id"] for i in page[0]["items"]] == [filed["id"]]
    # Today's three are unchanged: Home has no Needs Attention to repeat
    assert parked["id"] in [c["id"] for c in ai_client.get("/api/today").json()["recent"]]

    ai_client.post(f"/api/items/{parked['items'][0]['id']}/approve", json={"space": "home"})
    assert [c["id"] for c in ai_client.get("/api/recent").json()["captures"]] == [
        parked["id"],
        mixed["id"],
    ]


def test_attention_oldest_first(auth):
    first = one_item(auth, "first")["id"]
    second = one_item(auth, "second")["id"]
    assert ids(auth.get("/api/attention").json()) == [first, second]
    auth.post(f"/api/items/{first}/approve", json={"space": "home"})
    assert ids(auth.get("/api/attention").json()) == [second]


def test_spaces_come_from_config(auth):
    assert auth.get("/api/spaces").json()["spaces"] == SPACES.split(",")


def test_all_newest_first_with_filters_and_paging(auth):
    a = add(auth, "a", space="work", shape="task", title="A")
    b = add(auth, "b", space="home", shape="note")
    c = add(auth, "c", space="work", shape="note")
    pending = one_item(auth, "d")["id"]

    assert ids(auth.get("/api/items").json()) == [pending, c, b, a]
    assert ids(auth.get("/api/items", params={"space": "Work"}).json()) == [c, a]
    assert ids(auth.get("/api/items", params={"shape": "task"}).json()) == [a]
    assert ids(auth.get("/api/items", params={"space": "work", "shape": "note"}).json()) == [c]
    auth.patch(f"/api/items/{a}", json={"status": "done"})
    assert ids(auth.get("/api/items", params={"status": "done"}).json()) == [a]
    assert ids(auth.get("/api/items", params={"status": "open"}).json()) == []
    assert auth.get("/api/items", params={"status": "maybe"}).status_code == 422

    page = auth.get("/api/items", params={"limit": 2}).json()
    assert ids(page) == [pending, c] and page["next_before"] == c
    page = auth.get("/api/items", params={"limit": 2, "before": page["next_before"]}).json()
    assert ids(page) == [b, a] and page["next_before"] is None


def test_search_matches_text_and_title(auth):
    milk = add(auth, "buy milk and eggs", shape="task", title="Groceries")
    dentist = add(auth, "call the dentist", shape="task", title="Dentist appointment")
    add(auth, "unrelated note", shape="note")

    assert ids(auth.get("/api/items", params={"q": "milk"}).json()) == [milk]
    assert ids(auth.get("/api/items", params={"q": "groc"}).json()) == [milk]  # prefix, title
    assert ids(auth.get("/api/items", params={"q": "dentist"}).json()) == [dentist]
    assert ids(auth.get("/api/items", params={"q": "milk", "shape": "note"}).json()) == []
    assert auth.get("/api/items", params={"q": '"unbalanced AND (x'}).status_code == 200
    assert ids(auth.get("/api/items", params={"q": "zzz"}).json()) == []


def test_search_survives_title_edits_and_deletes(auth, settings):
    item = add(auth, "raw words", shape="task", title="first title")
    auth.patch(f"/api/items/{item}", json={"title": "second title"})
    assert ids(auth.get("/api/items", params={"q": "second"}).json()) == [item]
    assert ids(auth.get("/api/items", params={"q": "first"}).json()) == []
    conn = sqlite3.connect(settings.db_path)
    conn.execute("DELETE FROM items WHERE id = ?", (item,))
    conn.commit()
    assert ids(auth.get("/api/items", params={"q": "raw"}).json()) == []


@pytest.mark.parametrize(
    "q, expected",
    [
        ("", ""),
        ("   ", ""),
        ("milk", '"milk"*'),
        ("buy milk", '"buy" "milk"*'),
        ('say "hi"', '"say" """hi"""*'),
        ("AND OR", '"AND" "OR"*'),
    ],
)
def test_fts_query(q, expected):
    assert fts_query(q) == expected


def test_attention_lists_stale_open_tasks(auth, settings):
    fresh = add(auth, "fresh", shape="task", title="fresh")
    old = add(auth, "old", shape="task", title="old")
    done_old = add(auth, "done old", shape="task", title="done old", status="done")
    note_old = add(auth, "note old", shape="note")
    waiting = one_item(auth, "waiting")["id"]
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        "UPDATE items SET updated_at = '2026-08-01T00:00:00.000Z' WHERE id IN (?, ?, ?)",
        (old, done_old, note_old),
    )
    conn.commit()
    conn.close()
    body = auth.get("/api/attention").json()
    assert [i["id"] for i in body["items"]] == [waiting]
    assert [i["id"] for i in body["stale"]] == [old]
    assert body["stale_days"] == 14
    assert fresh not in [i["id"] for i in body["stale"]]


def test_config_is_read_only_view_of_settings(auth):
    body = auth.get("/api/config").json()
    assert body["tz"] == "UTC" and body["spaces"] == SPACES.split(",")
    assert body["ai"] is False and "fallback" not in body
    assert body["autofile_confidence"] == 0.85
    assert auth.patch("/api/config", json={"tz": "x"}).status_code == 405
