"""Slice 31: the title is the text's first line, and the AI's task title becomes line one."""

from __future__ import annotations

from tartib import db
from tartib.store import retitle, title_of
from tests.conftest import capture, proposal, set_classify_reply


def _file(ai_client, monkeypatch, text, title, shape="task"):
    set_classify_reply(
        monkeypatch, proposal(shape=shape, text=text, space="work", title=title, confidence=0.95)
    )
    cap = capture(ai_client, text)
    return cap, cap["items"][0]


def test_the_ai_title_becomes_line_one_and_the_capture_keeps_its_words(ai_client, monkeypatch):
    cap, item = _file(
        ai_client, monkeypatch, "need to call Ali about the car insurance", "Call Ali"
    )
    assert item["raw_text"] == "Call Ali\n\nneed to call Ali about the car insurance"
    assert item["title"] == "Call Ali"
    assert cap["raw_text"] == "need to call Ali about the car insurance"  # rule 1: untouched


def test_a_title_that_is_already_the_first_line_is_not_repeated(ai_client, monkeypatch):
    _, item = _file(ai_client, monkeypatch, "buy milk", "Buy milk")
    assert item["raw_text"] == "buy milk" and item["title"] == "buy milk"


def test_editing_line_one_renames_the_task(ai_client, monkeypatch):
    _, item = _file(ai_client, monkeypatch, "need to call Ali about it", "Call Ali")
    r = ai_client.patch(
        f"/api/items/{item['id']}", json={"text": "Phone Ali\n\nneed to call Ali about it"}
    )
    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Phone Ali"


def test_a_title_edit_rewrites_line_one_rather_than_adding_another(ai_client, monkeypatch):
    """The approval card edits the quoted title; that is an edit of line one, not a second title."""
    _, item = _file(ai_client, monkeypatch, "need to call Ali about it", "Call Ali")
    body = ai_client.patch(f"/api/items/{item['id']}", json={"title": "Phone Ali"}).json()
    assert body["raw_text"] == "Phone Ali\n\nneed to call Ali about it"
    assert body["title"] == "Phone Ali"


def test_a_note_is_named_by_its_first_line_and_keeps_no_title(ai_client, monkeypatch):
    _, item = _file(ai_client, monkeypatch, "ideas for the trip\nlisbon", None, shape="note")
    assert item["raw_text"] == "ideas for the trip\nlisbon" and item["title"] is None


def test_a_note_made_a_task_keeps_its_text_under_the_new_title(ai_client, monkeypatch):
    _, item = _file(ai_client, monkeypatch, "the lease runs out in may", None, shape="note")
    body = ai_client.patch(
        f"/api/items/{item['id']}", json={"shape": "task", "title": "Renew the lease"}
    ).json()
    assert body["raw_text"] == "Renew the lease\n\nthe lease runs out in may"
    assert body["title"] == "Renew the lease"


def test_redo_replaces_its_own_title_but_never_one_you_wrote(ai_client, monkeypatch):
    set_classify_reply(
        monkeypatch,
        proposal(
            shape="task",
            text="call Sara about the lease",
            space="work",
            title="Call Sara",
            confidence=0.4,
        ),
    )
    item = capture(ai_client, "call Sara about the lease")["items"][0]
    assert item["raw_text"].startswith("Call Sara\n\n")

    set_classify_reply(
        monkeypatch, proposal(shape="task", space="home", title="Ring Sara", confidence=0.4)
    )
    body = ai_client.post(f"/api/items/{item['id']}/redo", json={"reason": "home"}).json()
    assert body["raw_text"] == "Ring Sara\n\ncall Sara about the lease"  # its own line, replaced

    ai_client.patch(
        f"/api/items/{item['id']}", json={"text": "Sara, lease\n\ncall Sara about the lease"}
    )
    set_classify_reply(
        monkeypatch, proposal(shape="task", space="home", title="Phone Sara", confidence=0.4)
    )
    body = ai_client.post(f"/api/items/{item['id']}/redo", json={"reason": "again"}).json()
    assert body["raw_text"] == "Sara, lease\n\ncall Sara about the lease"  # yours: left alone
    assert body["title"] == "Sara, lease"


def test_title_of_takes_markdown_off_and_skips_blank_lines():
    assert title_of("\n\n# Plan **this**\nmore") == "Plan this"
    assert title_of("- [ ] ship it") == "ship it"
    assert title_of("   ") is None
    assert retitle("x", "  ") == "x"


def test_0018_puts_the_old_title_on_line_one_without_touching_updated_at(tmp_path):
    conn = db.connect(str(tmp_path / "v17.db"))
    db.migrate(conn, up_to=17)
    conn.execute(
        "INSERT INTO captures (id, raw_text, source, created_at, status)"
        " VALUES (1, 'x', 'web', '2026-09-01T10:00:00Z', 'done')"
    )
    rows = [
        (1, "task", "need to call Ali", "Call Ali"),  # differs: prepended
        (2, "task", "buy milk", "Buy milk"),  # case only: title follows the text
        (3, "task", "# Plan the trip", "Plan the trip"),  # a heading of the same words
        (4, "task", "water plants", None),  # no title: takes the first line
        (5, "note", "a note\nmore", None),  # notes are not touched
    ]
    for id_, shape, text, title in rows:
        conn.execute(
            "INSERT INTO items (id, capture_id, raw_text, space, shape, title, stage, created_at,"
            " updated_at) VALUES (?, 1, ?, 'work', ?, ?, 'filed', '2026-09-01T10:00:00Z',"
            " '2026-09-01T10:00:00Z')",
            (id_, text, shape, title),
        )
    conn.commit()

    assert db.migrate(conn) == 20
    got = {r["id"]: r for r in conn.execute("SELECT * FROM items")}
    assert (got[1]["raw_text"], got[1]["title"]) == ("Call Ali\n\nneed to call Ali", "Call Ali")
    assert (got[2]["raw_text"], got[2]["title"]) == ("buy milk", "buy milk")
    assert (got[3]["raw_text"], got[3]["title"]) == ("# Plan the trip", "Plan the trip")
    assert (got[4]["raw_text"], got[4]["title"]) == ("water plants", "water plants")
    assert (got[5]["raw_text"], got[5]["title"]) == ("a note\nmore", None)
    assert all(r["updated_at"] == "2026-09-01T10:00:00Z" for r in got.values())
    # The trigger is back: a real edit still moves updated_at.
    conn.execute("UPDATE items SET starred = 1 WHERE id = 1")
    assert (
        conn.execute("SELECT updated_at FROM items WHERE id = 1").fetchone()[0]
        != "2026-09-01T10:00:00Z"
    )
    conn.close()
