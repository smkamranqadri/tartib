"""The classifier proposes links (slice 33 phase C), behind TARTIB_LINK_PROPOSALS."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager

from fastapi.testclient import TestClient

from tartib.main import create_app
from tests.conftest import (
    AI_ENV,
    FAKE_VARS,
    PASSWORD,
    capture,
    make_settings,
    proposal,
    records,
    set_classify_reply,
)


@contextmanager
def linking_client(tmp_path, monkeypatch):
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    settings = make_settings(tmp_path, **AI_ENV, TARTIB_LINK_PROPOSALS="1")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        yield client


def linked(text, related, space="work", confidence=0.95, duplicate_of=None):
    p = proposal(shape="note", text=text, space=space, confidence=confidence)
    p["duplicate_of"] = duplicate_of
    p["new_space"] = None
    p["related"] = list(related)
    return p


def file_note(client, monkeypatch, text, space="work"):
    set_classify_reply(monkeypatch, proposal(shape="note", text=text, space=space))
    item = capture(client, text)["items"][0]
    assert item["stage"] == "filed"
    return item


def calls(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.row_factory = sqlite3.Row
    rows = conn.execute("SELECT * FROM ai_calls WHERE kind = 'classify' ORDER BY id").fetchall()
    conn.close()
    return rows


def test_off_the_prompt_asks_nothing_and_nothing_waits(ai_client, monkeypatch, tmp_path):
    """SABOTAGE GUARD. Off is the default and must be exactly what came before."""
    file_note(ai_client, monkeypatch, "docker setup for the server")
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(monkeypatch, linked("caprover setup needs docker setup", ["i1"]))
    item = capture(ai_client, "caprover setup needs docker setup")["items"][0]
    prompt = records(record)[-1]["argv"][-1]
    assert '"related"' not in prompt
    assert item["stage"] == "filed" and item["wait_reason"] is None
    assert "related" not in item["proposal"]
    assert calls(tmp_path)[-1]["links_on"] == 0


def test_on_a_proposed_link_waits_with_its_chip(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        docker = file_note(client, monkeypatch, "Docker setup for the server")
        record = tmp_path / "calls.jsonl"
        monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
        set_classify_reply(monkeypatch, linked("CapRover setup, after docker setup", ["i1", "i7"]))
        item = capture(client, "CapRover setup, after docker setup")["items"][0]
        assert '"related"' in records(record)[-1]["argv"][-1]
        assert item["stage"] == "attention" and item["wait_reason"] == "linked"
        assert item["proposal"]["related"] == [str(docker["id"])]  # the invented i7 is gone
        queue = client.get("/api/attention").json()["items"]
        card = next(i for i in queue if i["id"] == item["id"])
        assert card["related"] == [
            {"id": docker["id"], "title": "Docker setup for the server", "space": "work"}
        ]
        assert calls(tmp_path)[-1]["links_on"] == 1


def test_keeping_the_chip_writes_the_link(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        docker = file_note(client, monkeypatch, "Docker setup for the server")
        set_classify_reply(monkeypatch, linked("CapRover setup, after docker setup", ["i1"]))
        item = capture(client, "CapRover setup, after docker setup")["items"][0]
        r = client.post(f"/api/items/{item['id']}/approve", json={"links": [docker["id"]]})
        assert r.status_code == 200, r.text
        filed = r.json()
        assert filed["stage"] == "filed"
        assert filed["raw_text"].endswith("\n\nRelated: [[Docker setup for the server]]")
        target = client.get(f"/api/items/{docker['id']}").json()
        assert [i["id"] for i in target["linked_from"]] == [item["id"]]


def test_dropping_the_chip_files_without_a_link(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        file_note(client, monkeypatch, "Docker setup for the server")
        set_classify_reply(monkeypatch, linked("CapRover setup, after docker setup", ["i1"]))
        item = capture(client, "CapRover setup, after docker setup")["items"][0]
        filed = client.post(f"/api/items/{item['id']}/approve", json={"links": []}).json()
        assert filed["raw_text"] == "CapRover setup, after docker setup"
        assert filed["stage"] == "filed"


def test_approve_links_only_what_was_proposed(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        docker = file_note(client, monkeypatch, "Docker setup for the server")
        other = file_note(client, monkeypatch, "Unrelated shopping list")
        set_classify_reply(monkeypatch, linked("CapRover setup, after docker setup", ["i1"]))
        item = capture(client, "CapRover setup, after docker setup")["items"][0]
        filed = client.post(
            f"/api/items/{item['id']}/approve", json={"links": [other["id"], docker["id"]]}
        ).json()
        assert filed["raw_text"].endswith("Related: [[Docker setup for the server]]")


def test_a_file_space_files_and_keeps_the_proposal(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        client.put("/api/spaces/home/policy", json={"policy": "file"})
        docker = file_note(client, monkeypatch, "Docker setup at home", space="home")
        set_classify_reply(monkeypatch, linked("home server docker setup", ["i1"], space="home"))
        item = capture(client, "home server docker setup")["items"][0]
        assert item["stage"] == "filed" and item["wait_reason"] is None
        assert item["proposal"]["related"] == [str(docker["id"])]


def test_the_duplicate_is_not_also_related(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        file_note(client, monkeypatch, "Docker setup for the server")
        set_classify_reply(
            monkeypatch, linked("docker setup for the server again", ["i1"], duplicate_of="i1")
        )
        item = capture(client, "docker setup for the server again")["items"][0]
        assert "related" not in item["proposal"]
        assert item["wait_reason"] != "linked"


def test_a_low_confidence_item_keeps_its_own_reason_and_the_chip(tmp_path, monkeypatch):
    with linking_client(tmp_path, monkeypatch) as client:
        file_note(client, monkeypatch, "Docker setup for the server")
        set_classify_reply(
            monkeypatch, linked("CapRover setup, after docker setup", ["i1"], confidence=0.4)
        )
        item = capture(client, "CapRover setup, after docker setup")["items"][0]
        assert item["wait_reason"] == "low_confidence"
        queue = client.get("/api/attention").json()["items"]
        card = next(i for i in queue if i["id"] == item["id"])
        assert len(card["related"]) == 1
