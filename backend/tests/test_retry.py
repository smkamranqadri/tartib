"""A capture that failed to classify goes again once the classifier answers, a few times at most."""

from __future__ import annotations

import sqlite3
import time

import pytest
from fastapi.testclient import TestClient

from tartib import db
from tartib import runner as runner_module
from tartib.main import create_app
from tartib.runner import MAX_RETRIES, Runner
from tests.conftest import (
    AI_ENV,
    FAKE_VARS,
    PASSWORD,
    capture,
    make_settings,
    proposal,
    set_classify_reply,
)


@pytest.fixture
def fast_probe(monkeypatch):
    monkeypatch.setattr(runner_module, "RETRY_INTERVAL", 0.2)


@pytest.fixture
def ai(tmp_path, monkeypatch):
    for var in FAKE_VARS:
        monkeypatch.delenv(var, raising=False)
    settings = make_settings(tmp_path, **AI_ENV)
    with TestClient(create_app(settings)) as c:
        c.headers["Authorization"] = f"Bearer {PASSWORD}"
        c.db_path = settings.db_path
        yield c


def fail(monkeypatch, client, text):
    monkeypatch.setenv("FAKE_CODEX_EXIT", "3")
    cap = capture(client, text)
    assert cap["status"] == "error" and cap["items"][0]["proposal_error"], cap
    return cap


def recover(monkeypatch):
    monkeypatch.delenv("FAKE_CODEX_EXIT")
    set_classify_reply(monkeypatch, proposal(space="work"))


def until(check, timeout=6.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(0.05)
    raise AssertionError("condition never held")


def attempts(client, capture_id):
    conn = sqlite3.connect(client.db_path)
    try:
        return conn.execute("SELECT attempts FROM captures WHERE id = ?", (capture_id,)).fetchone()[
            0
        ]
    finally:
        conn.close()


def get(client, capture_id):
    return client.get(f"/api/captures/{capture_id}").json()


def test_a_success_sends_the_failed_ones_again(ai, monkeypatch):
    failed = fail(monkeypatch, ai, "call the plumber")
    recover(monkeypatch)
    capture(ai, "something new")

    done = until(lambda: (c := get(ai, failed["id"]))["status"] == "done" and c)
    assert [i["stage"] for i in done["items"]] == ["filed"]
    assert done["items"][0]["id"] != failed["items"][0]["id"]  # the fallback note is gone
    assert attempts(ai, failed["id"]) == 1


def test_the_probe_finds_them_without_a_new_capture(fast_probe, ai, monkeypatch):
    failed = fail(monkeypatch, ai, "renew the passport")
    recover(monkeypatch)
    until(lambda: get(ai, failed["id"])["status"] == "done")


def test_one_that_always_fails_stops_after_three(fast_probe, ai, monkeypatch):
    failed = fail(monkeypatch, ai, "this one never works")
    until(lambda: attempts(ai, failed["id"]) == MAX_RETRIES)
    time.sleep(0.6)  # three more probe periods
    assert attempts(ai, failed["id"]) == MAX_RETRIES
    cap = get(ai, failed["id"])
    assert cap["status"] == "error" and cap["items"][0]["stage"] == "attention"


@pytest.mark.parametrize(
    "edit", [{"starred": True}, {"title": "Mine now"}, {"shape": "task"}, {"space": "home"}]
)
def test_an_item_someone_has_touched_is_left_alone(ai, monkeypatch, edit):
    failed = fail(monkeypatch, ai, "sort the receipts")
    item_id = failed["items"][0]["id"]
    assert ai.patch(f"/api/items/{item_id}", json=edit).status_code == 200
    recover(monkeypatch)
    capture(ai, "something new")

    time.sleep(0.3)
    cap = get(ai, failed["id"])
    assert cap["status"] == "error" and [i["id"] for i in cap["items"]] == [item_id]
    assert attempts(ai, failed["id"]) == 0


def test_ai_off_is_not_a_failure_to_retry(auth, settings):
    cap = capture(auth, "no classifier here")
    assert cap["status"] == "error"
    assert Runner(settings)._reset_failed() == []


# --- the retry probe must not throw away work the owner did on a failed item ---


def _failed_capture_with(conn, *, thought: str | None = None, feedback: str | None = None):
    """A capture that failed to classify, its fallback note, and optionally the owner's work."""
    at = "2026-09-22T09:00:00Z"
    text = "buy milk and call the plumber"
    cur = conn.execute(
        "INSERT INTO captures (raw_text, status, error, created_at, attempts)"
        " VALUES (?, 'error', 'exit 1: boom', ?, 0)",
        (text, at),
    )
    capture_id = cur.lastrowid
    conn.execute(
        "INSERT INTO items (capture_id, raw_text, shape, space, title, due, remind_at, starred,"
        " status, stage, created_at, updated_at, proposal_json, proposal_error, feedback)"
        " VALUES (?, ?, 'note', NULL, NULL, NULL, NULL, 0, 'open', 'attention', ?, ?, NULL,"
        " 'exit 1: boom', ?)",
        (capture_id, text, at, at, feedback),
    )
    item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    if thought:
        conn.execute(
            "INSERT INTO item_thoughts (item_id, body, created_at) VALUES (?, ?, ?)",
            (item_id, thought, at),
        )
    conn.commit()
    return capture_id, item_id


def test_a_failed_item_carrying_a_thought_is_never_retried(tmp_path):
    """The retry deletes the item, and item_thoughts cascades. Adding a thought changes none of
    the eleven fields the guard checked, so the owner's note was destroyed silently."""
    settings = make_settings(tmp_path)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    _failed_capture_with(conn, thought="actually about the leak in the roof, not groceries")

    assert Runner(settings)._reset_failed() == []

    assert conn.execute("SELECT COUNT(*) FROM item_thoughts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
    assert conn.execute("SELECT status FROM captures").fetchone()[0] == "error"
    conn.close()


def test_a_failed_item_carrying_a_redo_reason_is_never_retried(tmp_path):
    """`feedback` is the only record of why a proposal was wrong (rule 8). Same reasoning."""
    settings = make_settings(tmp_path)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    _failed_capture_with(conn, feedback="2026-09-22: this is not a grocery thing")

    assert Runner(settings)._reset_failed() == []
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 1
    conn.close()


def test_an_untouched_failed_item_is_still_retried(tmp_path):
    """The guard must not become so strict that the retry never fires."""
    settings = make_settings(tmp_path)
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    capture_id, _ = _failed_capture_with(conn)

    assert Runner(settings)._reset_failed() == [capture_id]
    assert conn.execute("SELECT COUNT(*) FROM items").fetchone()[0] == 0
    assert conn.execute("SELECT status FROM captures").fetchone()[0] == "pending"
    conn.close()
