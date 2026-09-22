"""A v1 database (items only, 'inbox' space, inbox stage) migrates to captures + items."""

import sqlite3

from fastapi.testclient import TestClient

from tartib import db
from tartib.main import create_app
from tests.conftest import PASSWORD, capture, make_settings

V1_ROWS = [
    # id, raw_text, space, shape, stage, title, proposal_json
    (
        1,
        "filed task",
        "work",
        "task",
        "filed",
        "Filed task",
        '{"shape":"task","space":"work","confidence":0.9}',
    ),
    (2, "rejected note", "inbox", "note", "filed", None, None),
    (
        3,
        "waiting with proposal",
        "inbox",
        "note",
        "attention",
        None,
        '{"shape":"note","space":"ideas","confidence":0.5}',
    ),
    (4, "never classified", "inbox", "note", "inbox", None, None),
    (5, "filed note", "home", "note", "filed", None, None),
]


def build_v1(path: str) -> None:
    conn = db.connect(path)
    db.migrate(conn, up_to=1)
    for id_, text, space, shape, stage, title, pj in V1_ROWS:
        conn.execute(
            "INSERT INTO items (id, raw_text, space, shape, stage, created_at, title,"
            " proposal_json) VALUES (?, ?, ?, ?, ?, '2026-09-10T10:00:00Z', ?, ?)",
            (id_, text, space, shape, stage, title, pj),
        )
    conn.commit()
    conn.close()


def test_v1_to_v2(tmp_path):
    path = str(tmp_path / "v1.db")
    build_v1(path)
    conn = db.connect(path)
    assert db.migrate(conn) == 16
    assert conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 16

    caps = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM captures ORDER BY id")}
    assert len(caps) == 5
    assert all(c["source"] == "migrated" for c in caps.values())
    assert caps[4]["status"] == "pending" and caps[1]["status"] == "done"
    assert caps[4]["raw_text"] == "never classified"

    items = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM items ORDER BY id")}
    assert set(items) == {1, 2, 3, 5}  # the unclassified placeholder is gone
    assert all(items[i]["capture_id"] == i for i in items)
    assert items[1]["space"] == "work" and items[1]["stage"] == "filed"
    assert items[5]["space"] == "home" and items[5]["stage"] == "filed"
    assert items[2]["space"] is None and items[2]["stage"] == "attention"
    assert items[3]["space"] is None and items[3]["stage"] == "attention"
    assert items[3]["proposal_json"] is not None  # proposal kept for the human

    # FTS rebuilt and triggers live
    hit = conn.execute(
        "SELECT rowid FROM items_fts WHERE items_fts MATCH '\"rejected\"'"
    ).fetchall()
    assert [h[0] for h in hit] == [2]
    conn.execute("UPDATE items SET title = 'Zebra' WHERE id = 5")
    assert (
        conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'zebra'").fetchone()[0] == 5
    )
    conn.execute("UPDATE items SET raw_text = 'edited text' WHERE id = 1")
    assert (
        conn.execute("SELECT rowid FROM items_fts WHERE items_fts MATCH 'edited'").fetchone()[0]
        == 1
    )
    try:
        conn.execute("UPDATE items SET space = NULL WHERE id = 1")
        raise AssertionError("filed items need a space")
    except sqlite3.IntegrityError:
        pass
    conn.close()

    # the app boots on it, re-classifies the pending capture, and serves the migrated rows
    settings = make_settings(tmp_path, TARTIB_DB_PATH=path)
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        from tests.conftest import wait_capture

        cap4 = wait_capture(client, 4)
        assert cap4["status"] == "error" and len(cap4["items"]) == 1  # AI off fallback
        attention = client.get("/api/attention").json()["items"]
        assert [i["id"] for i in attention][:2] == [2, 3]
        assert client.get("/api/items", params={"q": "filed"}).json()["items"]
        new = capture(client, "post-migration capture")
        assert new["id"] == 6


def test_unconfigured_spaces_move_to_attention_on_startup(tmp_path):
    path = str(tmp_path / "v1.db")
    build_v1(path)
    settings = make_settings(tmp_path, TARTIB_DB_PATH=path, TARTIB_SPACES="work,ideas")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        five = client.get("/api/items/5").json()  # was filed in 'home', not configured now
        assert five["space"] is None and five["stage"] == "attention"
        one = client.get("/api/items/1").json()  # 'work' is configured, untouched
        assert one["space"] == "work" and one["stage"] == "filed"
        assert client.get("/api/items", params={"space": "home"}).json()["items"] == []


def test_migrate_is_idempotent(tmp_path):
    path = str(tmp_path / "v.db")
    build_v1(path)
    conn = db.connect(path)
    db.migrate(conn)
    assert db.migrate(conn) == 16
    assert conn.execute("SELECT COUNT(*) FROM captures").fetchone()[0] == 5


def test_0005_writes_off_reminders_that_are_already_due(tmp_path):
    """The first tick after this deploy must be silent, not a replay of every past reminder."""
    path = str(tmp_path / "v4.db")
    conn = db.connect(path)
    db.migrate(conn, up_to=4)
    conn.execute(
        "INSERT INTO captures (id, raw_text, source, created_at, status)"
        " VALUES (1, 'x', 'migrated', '2026-09-01T10:00:00Z', 'done')"
    )
    for id_, remind_at in ((1, "2026-01-01T10:00:00Z"), (2, "2099-01-01T10:00:00Z"), (3, None)):
        conn.execute(
            "INSERT INTO items (id, capture_id, raw_text, space, shape, stage, created_at,"
            " updated_at, remind_at) VALUES (?, 1, 'x', 'work', 'task', 'filed',"
            " '2026-09-01T10:00:00Z', '2026-09-01T10:00:00Z', ?)",
            (id_, remind_at),
        )
    conn.commit()

    assert db.migrate(conn) == 16
    rows = {r["id"]: dict(r) for r in conn.execute("SELECT * FROM items")}
    assert rows[1]["reminded_at"] is not None  # already due: written off
    assert rows[2]["reminded_at"] is None  # still ahead: will fire
    assert rows[3]["reminded_at"] is None
    # Writing the backfill must not look like someone touched these items.
    assert all(r["updated_at"] == "2026-09-01T10:00:00Z" for r in rows.values())
    conn.close()
