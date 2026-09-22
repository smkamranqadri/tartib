"""Suggest links for items already filed (slice 34), on the fake model."""

from __future__ import annotations

import asyncio
import sqlite3

import pytest

from tartib import db
from tartib.reclassify import select_ids
from tartib.suggest_links import run
from tests.conftest import AI_ENV, make_settings, proposal, set_classify_reply, wait_capture


def reply_related(monkeypatch, *labels):
    p = proposal(shape="note", text="x", space="work", confidence=0.95)
    p.update(duplicate_of=None, new_space=None, related=list(labels))
    set_classify_reply(monkeypatch, p)


def add(client, text, shape="note", space="work"):
    r = client.post("/api/items", json={"shape": shape, "space": space, "text": text})
    assert r.status_code == 201, r.text
    return r.json()


def rows(tmp_path, sql, *args):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    out = conn.execute(sql, args).fetchall()
    conn.close()
    return out


def go(tmp_path, space="work", limit=20, dry_run=False):
    return asyncio.run(run(make_settings(tmp_path, **AI_ENV), space, limit, dry_run))


@pytest.fixture
def pair(ai_client):
    """Two filed notes that find each other as similar: each one's i1 is the other."""
    docker = add(ai_client, "Docker setup on the server")
    caprover = add(ai_client, "CapRover setup on the server after docker")
    return ai_client, docker, caprover


def test_a_dry_run_stores_nothing(pair, monkeypatch, tmp_path):
    client, docker, caprover = pair
    reply_related(monkeypatch, "i1")
    report = go(tmp_path, dry_run=True)
    assert report.items == 2 and report.suggested == 1 and report.links == 1
    assert rows(tmp_path, "SELECT * FROM link_suggestions") == []
    assert rows(tmp_path, "SELECT * FROM ai_calls") == []
    assert {i["stage"] for i in (client.get(f"/api/items/{x['id']}").json() for x in pair[1:])} == {
        "filed"
    }


def test_a_run_sends_back_one_per_pair(pair, monkeypatch, tmp_path):
    client, docker, caprover = pair
    reply_related(monkeypatch, "i1")
    report = go(tmp_path)
    assert report.suggested == 1 and report.links == 1
    stored = rows(tmp_path, "SELECT item_id, target_id, state FROM link_suggestions")
    assert [tuple(r) for r in stored] == [(caprover["id"], docker["id"], "pending")]
    back = client.get(f"/api/items/{caprover['id']}").json()
    assert back["stage"] == "attention" and back["wait_reason"] == "relink"
    assert client.get(f"/api/items/{docker['id']}").json()["stage"] == "filed"
    queue = client.get("/api/attention").json()["items"]
    card = next(i for i in queue if i["id"] == caprover["id"])
    assert card["related"] == [
        {"id": docker["id"], "title": "Docker setup on the server", "space": "work"}
    ]
    calls = rows(tmp_path, "SELECT kind, links_on FROM ai_calls")
    assert [tuple(c) for c in calls] == [("relink", 1), ("relink", 1)]


def test_approving_files_it_back_as_it_was(ai_client, monkeypatch, tmp_path):
    set_classify_reply(
        monkeypatch, proposal(shape="task", text="book the dentist", space="work", title="Book")
    )
    r = ai_client.post("/api/capture", json={"text": "book the dentist for sunday"})
    task = wait_capture(ai_client, r.json()["id"])["items"][0]
    target = add(ai_client, "Dentist notes, the clinic on sunday", space="health")
    # Edited after the note exists, so the task is the most recently touched and goes first.
    ai_client.patch(f"/api/items/{task['id']}", json={"space": "health", "due": "2026-10-01"})
    own = "SELECT classified_at, proposal_json FROM items WHERE id = ?"
    before = rows(tmp_path, own, task["id"])
    reply_related(monkeypatch, "i1")
    go(tmp_path, space="health")
    got = ai_client.get(f"/api/items/{task['id']}").json()
    assert got["wait_reason"] == "relink"
    filed = ai_client.post(f"/api/items/{task['id']}/approve", json={"links": [target["id"]]})
    assert filed.status_code == 200, filed.text
    f = filed.json()
    assert f["stage"] == "filed" and f["wait_reason"] is None
    assert f["space"] == "health" and f["due"] == "2026-10-01"  # its own, not the proposal's
    assert f["raw_text"].endswith("\n\nRelated: [[Dentist notes, the clinic on sunday]]")
    after = rows(tmp_path, own, task["id"])
    assert tuple(after[0]) == tuple(before[0])
    state = rows(tmp_path, "SELECT state FROM link_suggestions")
    assert [r["state"] for r in state] == ["kept"]


def test_a_skipped_pair_is_never_suggested_again(pair, monkeypatch, tmp_path):
    client, docker, caprover = pair
    reply_related(monkeypatch, "i1")
    go(tmp_path)
    r = client.post(f"/api/items/{caprover['id']}/approve", json={"links": []})
    assert r.json()["raw_text"] == "CapRover setup on the server after docker"
    assert [x["state"] for x in rows(tmp_path, "SELECT state FROM link_suggestions")] == ["skipped"]
    # Changed text is asked about again; the pair still is not offered again.
    client.patch(f"/api/items/{caprover['id']}", json={"text": "CapRover setup on the server"})
    report = go(tmp_path)
    assert report.items == 1 and report.suggested == 0
    assert client.get(f"/api/items/{docker['id']}").json()["stage"] == "filed"


def test_an_existing_link_counts_as_the_pair(ai_client, monkeypatch, tmp_path):
    add(ai_client, "Docker setup on the server")
    add(ai_client, "CapRover setup on the server, see [[Docker setup on the server]]")
    reply_related(monkeypatch, "i1")
    assert go(tmp_path).suggested == 0


def test_a_relink_item_is_never_reclassified(pair, monkeypatch, tmp_path, settings):
    client, docker, caprover = pair
    reply_related(monkeypatch, "i1")
    go(tmp_path)
    r = client.post(f"/api/items/{caprover['id']}/redo", json={"reason": "wrong"})
    assert r.status_code == 409
    conn = db.connect(str(tmp_path / "t.db"))
    assert caprover["capture_id"] not in select_ids(conn, "attention")
    conn.close()


def test_limit_and_space(pair, monkeypatch, tmp_path):
    reply_related(monkeypatch)
    assert go(tmp_path, limit=1).items == 1
    with pytest.raises(SystemExit):
        go(tmp_path, space="nowhere")


def test_an_invented_label_suggests_nothing(pair, monkeypatch, tmp_path):
    reply_related(monkeypatch, "i9")
    assert go(tmp_path).suggested == 0
    assert rows(tmp_path, "SELECT count(*) c FROM link_suggestions")[0]["c"] == 0


def test_an_unchanged_item_is_not_asked_again(pair, monkeypatch, tmp_path):
    reply_related(monkeypatch)
    assert go(tmp_path).items == 2
    assert go(tmp_path).items == 0  # nothing changed: no calls
    assert len(rows(tmp_path, "SELECT * FROM ai_calls")) == 2
    client, docker, _ = pair
    client.patch(f"/api/items/{docker['id']}", json={"text": "Docker setup on the new server"})
    assert go(tmp_path).items == 1


def test_a_task_with_a_reminder_to_come_is_left_alone(ai_client, monkeypatch, tmp_path):
    task = add(ai_client, "Renew the server certificate", shape="task")
    ai_client.patch(f"/api/items/{task['id']}", json={"remind_at": "2099-01-01T09:00:00Z"})
    add(ai_client, "Server certificate notes")
    reply_related(monkeypatch, "i1")
    report = go(tmp_path)
    assert report.items == 1
    assert ai_client.get(f"/api/items/{task['id']}").json()["stage"] == "filed"


def test_suggest_leaves_what_changed_meanwhile_alone(pair, tmp_path):
    from tartib.store import suggest

    client, docker, caprover = pair
    other = add(client, "Another server note")
    client.delete(f"/api/items/{docker['id']}")
    conn = db.connect(str(tmp_path / "t.db"))
    assert suggest(conn, caprover["id"], [docker["id"]]) == []  # the target went
    conn.execute("UPDATE items SET stage = 'attention' WHERE id = ?", (caprover["id"],))
    assert suggest(conn, caprover["id"], [other["id"]]) == []  # no longer filed
    conn.rollback()
    conn.close()
    assert rows(tmp_path, "SELECT count(*) c FROM link_suggestions")[0]["c"] == 0
