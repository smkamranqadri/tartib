"""Today (tasks + recent captures), Needs Attention, All, spaces."""

import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from tartib.queries import fts_query
from tests.conftest import SPACES, capture, one_item


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


def test_today_recent_captures(auth, settings):
    caps = [capture(auth, f"note {i}")["id"] for i in range(5)]
    conn = sqlite3.connect(settings.db_path)
    # push two captures to yesterday
    conn.execute(
        "UPDATE captures SET created_at = ? WHERE id IN (?, ?)",
        (
            (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z"),
            caps[0],
            caps[1],
        ),
    )
    conn.commit()
    conn.close()
    recent = auth.get("/api/today").json()["recent"]
    # the three captured today, newest first; the older two are not the newest 3 so excluded
    assert [c["id"] for c in recent] == [caps[4], caps[3], caps[2]]
    assert recent[0]["raw_text"] == "note 4"
    assert recent[0]["status"] == "error" and len(recent[0]["items"]) == 1
    assert recent[0]["items"][0]["stage"] == "attention"

    # nothing captured today: still the newest 3
    conn = sqlite3.connect(settings.db_path)
    conn.execute(
        "UPDATE captures SET created_at = ?",
        ((datetime.now(UTC) - timedelta(days=2)).isoformat().replace("+00:00", "Z"),),
    )
    conn.commit()
    conn.close()
    assert [c["id"] for c in auth.get("/api/today").json()["recent"]] == [caps[4], caps[3], caps[2]]


def test_attention_oldest_first(auth):
    first = one_item(auth, "first")["id"]
    second = one_item(auth, "second")["id"]
    assert ids(auth.get("/api/attention").json()) == [first, second]
    auth.post(f"/api/items/{first}/approve", json={"space": "home"})
    assert ids(auth.get("/api/attention").json()) == [second]


def test_spaces_come_from_config(auth):
    assert auth.get("/api/spaces").json() == {"spaces": SPACES.split(",")}


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
