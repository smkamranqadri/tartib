"""Today, Needs Attention, All. AI disabled: captures park in attention, tests approve them."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from tartib.queries import fts_query
from tests.test_classify import wait_classified


def add(auth, text, **fields):
    item_id = auth.post("/api/capture", json={"text": text}).json()["id"]
    wait_classified(auth, item_id)
    if fields:
        auth.post(f"/api/items/{item_id}/approve", json=fields)
    return item_id


def ids(payload):
    return [i["id"] for i in payload["items"]]


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
    note = add(auth, "h", shape="note", space="x")
    done = add(auth, "i", shape="task", title="i", due=today.isoformat(), status="done")
    pending = auth.post("/api/capture", json={"text": "j"}).json()["id"]
    wait_classified(auth, pending)  # stays in attention

    payload = auth.get("/api/today").json()
    assert payload["date"] == today.isoformat()
    got = set(ids(payload))
    assert got == {due_today, overdue, starred, reminded}
    for absent in (later, reminder_later, plain_task, note, done, pending):
        assert absent not in got
    assert ids(payload)[:2] == [overdue, due_today]  # overdue first


def test_attention_oldest_first(auth):
    first = auth.post("/api/capture", json={"text": "first"}).json()["id"]
    second = auth.post("/api/capture", json={"text": "second"}).json()["id"]
    wait_classified(auth, second)
    wait_classified(auth, first)
    assert ids(auth.get("/api/attention").json()) == [first, second]
    auth.post(f"/api/items/{first}/reject")
    assert ids(auth.get("/api/attention").json()) == [second]


def test_spaces_are_filed_only(auth):
    add(auth, "a", space="work", shape="note")
    add(auth, "b", space="work", shape="note")
    add(auth, "c", space="home", shape="note")
    auth.post("/api/capture", json={"text": "d"})
    assert auth.get("/api/spaces").json() == {"spaces": ["work", "home"]}


def test_all_newest_first_with_filters_and_paging(auth):
    a = add(auth, "a", space="work", shape="task", title="A")
    b = add(auth, "b", space="home", shape="note")
    c = add(auth, "c", space="work", shape="note")
    pending = auth.post("/api/capture", json={"text": "d"}).json()["id"]
    wait_classified(auth, pending)

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


def test_search_survives_title_edits(auth, settings):
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
