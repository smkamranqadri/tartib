import asyncio
import json

from fastapi.testclient import TestClient

from tartib.main import create_app
from tartib.reclassify import reclassify
from tests.conftest import (
    AI_ENV,
    PASSWORD,
    capture,
    make_settings,
    proposal,
    set_ask_reply,
    set_classify_reply,
)


def seed(tmp_path, monkeypatch):
    """Three captures: a filed task marked done+starred, one waiting, one question."""
    settings = make_settings(tmp_path, **AI_ENV)
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        set_classify_reply(
            monkeypatch, proposal(shape="task", text="pay rent", space="home", title="Pay rent")
        )
        task = capture(client, "pay rent")["items"][0]
        client.patch(
            f"/api/items/{task['id']}", json={"status": "done", "starred": True, "title": "Rent!"}
        )
        set_classify_reply(
            monkeypatch, proposal(shape="note", text="hmm", space=None, confidence=0.3)
        )
        waiting = capture(client, "hmm")
        set_classify_reply(monkeypatch, proposal(shape="question", text="rent?"))
        set_ask_reply(monkeypatch, "Rent is paid.", [task["id"]])
        question = capture(client, "rent?")
    return settings, task, waiting, question


def test_reclassify_all_rebuilds_items_and_carries_flags(tmp_path, monkeypatch):
    settings, task, waiting, question = seed(tmp_path, monkeypatch)
    # new classifier behaviour: the rent capture now splits in two, "hmm" gets a space
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY_CLASSIFY",
        json.dumps(
            {
                "proposals": [
                    proposal(shape="task", text="pay", space="finance", title="Pay"),
                    proposal(shape="note", text="rent", space="home"),
                ]
            }
        ),
    )
    report = asyncio.run(reclassify(settings, "all"))
    assert report.selected == 3 and report.reset == 3
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        rent = client.get(f"/api/captures/{task['capture_id']}").json()
        assert [i["title"] for i in rent["items"]] == ["pay", None]
        assert rent["items"][0]["status"] == "open"  # split into two: flags not carried
        assert report.carried == 0
        # the old item is gone (SQLite may reuse its id for a rebuilt one)
        titles = [i["title"] for i in client.get("/api/items").json()["items"]]
        assert "Rent!" not in titles
        hmm = client.get(f"/api/captures/{waiting['id']}").json()
        assert len(hmm["items"]) == 2 and hmm["status"] == "done"
        q = client.get(f"/api/captures/{question['id']}").json()
        # the fake now files everything as two items, so the old answer is gone with the old run
        assert q["answer"] is None and len(q["items"]) == 2


def test_reclassify_carries_done_and_star_for_single_task(tmp_path, monkeypatch):
    settings, task, *_ = seed(tmp_path, monkeypatch)
    set_classify_reply(
        monkeypatch, proposal(shape="task", text="pay rent", space="finance", title="Pay rent")
    )
    report = asyncio.run(reclassify(settings, "all"))
    assert report.carried == 1
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        [item] = client.get(f"/api/captures/{task['capture_id']}").json()["items"]
        # The manual title is not kept: the rebuilt text is the title.
        assert item["space"] == "finance" and item["title"] == "pay rent"
        assert item["status"] == "done" and item["starred"] is True


def test_reclassify_attention_scope_and_dry_run(tmp_path, monkeypatch):
    settings, task, waiting, question = seed(tmp_path, monkeypatch)
    report = asyncio.run(reclassify(settings, "attention", dry_run=True))
    assert report.selected == 1 and report.reset == 0
    set_classify_reply(monkeypatch, proposal(shape="note", text="hmm", space="ideas"))
    report = asyncio.run(reclassify(settings, "attention"))
    assert report.reset == 1 and report.items_filed == 1
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        assert client.get(f"/api/items/{task['id']}").json()["status"] == "done"  # untouched
        assert client.get(f"/api/captures/{waiting['id']}").json()["items"][0]["space"] == "ideas"


def test_reclassify_leaves_alone_a_capture_someone_wrote_a_thought_on(settings):
    """Reclassifying deletes items and item_thoughts cascades. A thought is one of the two
    things here the classifier did not write, so it is one it must never take back."""
    from tartib import db
    from tartib.reclassify import count_skipped, select_ids

    conn = db.connect(settings.db_path)
    db.migrate(conn)
    at = "2026-09-22T09:00:00Z"
    ids = []
    for body in (None, "this is about the roof, not groceries"):
        cur = conn.execute(
            "INSERT INTO captures (raw_text, status, created_at) VALUES ('x', 'done', ?)", (at,)
        )
        cid = cur.lastrowid
        conn.execute(
            "INSERT INTO items (capture_id, raw_text, shape, stage, status, created_at,"
            " updated_at) VALUES (?, 'x', 'note', 'attention', 'open', ?, ?)",
            (cid, at, at),
        )
        item_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        if body:
            conn.execute(
                "INSERT INTO item_thoughts (item_id, body, created_at) VALUES (?, ?, ?)",
                (item_id, body, at),
            )
        conn.commit()
        ids.append(cid)

    selected = select_ids(conn, "attention")
    assert ids[0] in selected  # untouched: still fair game
    assert ids[1] not in selected  # carries a thought: left alone
    assert count_skipped(conn) == 1
    conn.close()
