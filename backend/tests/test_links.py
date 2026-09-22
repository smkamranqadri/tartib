"""Links between items (slice 33): `[[Title]]` in the text, what it opens, what links back, and
renaming the target rewriting the link."""

from __future__ import annotations

import sqlite3

from tartib import db
from tartib.store import links_in, reindex_links, relink


def add(client, text, shape="note", space="work"):
    r = client.post("/api/items", json={"shape": shape, "space": space, "text": text})
    assert r.status_code == 201, r.text
    return r.json()


def get(client, item_id):
    return client.get(f"/api/items/{item_id}").json()


def edit(client, item_id, text, **extra):
    return client.patch(f"/api/items/{item_id}", json={"text": text, **extra})


def test_the_grammar():
    assert links_in("see [[Docker setup]] and [[docker  SETUP]], then [[**Server**]]") == [
        "docker setup",
        "server",
    ]
    assert links_in("`[[not a link]]`\n\n```\n[[nor this]]\n```\n[[yes]]") == ["yes"]
    assert links_in("```\n[[unclosed fence]]") == []
    assert links_in("[[]] [[a\nb]] [single]") == []
    assert relink("[[Old]] `[[Old]]` [[old]] [[Other]]", "old", "New") == (
        "[[New]] `[[Old]]` [[New]] [[Other]]"
    )


def test_a_link_opens_its_target_and_a_missing_one_is_null(auth):
    docker = add(auth, "Docker setup\n\ninstall docker")
    caprover = add(auth, "CapRover setup\n\nfirst [[docker setup]], then [[Nowhere]]")
    got = get(auth, caprover["id"])
    assert got["links"] == {"docker setup": docker["id"], "Nowhere": None}
    assert got["linked_from"] == []


def test_the_target_shows_what_links_to_it(auth):
    server = add(auth, "Server setup")
    docker = add(auth, "Docker setup\n\nneeds [[Server setup]]", shape="task")
    add(auth, "Unrelated")
    got = get(auth, server["id"])
    assert [i["id"] for i in got["linked_from"]] == [docker["id"]]


def test_two_items_with_one_title_the_newest_wins(auth):
    older = add(auth, "Checklist")
    newer = add(auth, "Checklist", space="home")
    src = add(auth, "see [[Checklist]]")
    assert get(auth, src["id"])["links"] == {"Checklist": newer["id"]}
    assert [i["id"] for i in get(auth, newer["id"])["linked_from"]] == [src["id"]]
    assert get(auth, older["id"])["linked_from"] == []
    edit(auth, older["id"], "Checklist\n\ntouched")  # now the most recently touched
    assert get(auth, src["id"])["links"] == {"Checklist": older["id"]}


def test_renaming_the_target_rewrites_the_link(auth, settings):
    docker = add(auth, "Docker setup\n\ninstall docker")
    src = add(auth, "CapRover setup\n\nfirst [[Docker setup]], keep `[[Docker setup]]`")
    loaded = get(auth, src["id"])["updated_at"]
    r = edit(auth, docker["id"], "Docker install\n\ninstall docker")
    assert r.status_code == 200
    after = get(auth, src["id"])
    assert after["raw_text"] == (
        "CapRover setup\n\nfirst [[Docker install]], keep `[[Docker setup]]`"
    )
    assert after["links"] == {"Docker install": docker["id"]}
    assert [i["id"] for i in get(auth, docker["id"])["linked_from"]] == [src["id"]]
    # An editor opened on the linking note before the rename is told, not overwritten.
    assert after["updated_at"] != loaded
    stale = edit(auth, src["id"], "mine", expected_updated_at=loaded)
    assert stale.status_code == 409
    # What was captured stays as typed (rule 1).
    conn = sqlite3.connect(settings.db_path)
    typed = conn.execute(
        "SELECT c.raw_text FROM captures c JOIN items i ON i.capture_id = c.id WHERE i.id = ?",
        (src["id"],),
    ).fetchone()[0]
    conn.close()
    assert "[[Docker setup]]" in typed


def test_a_task_rename_through_the_title_rewrites_too(auth):
    task = add(auth, "Buy milk", shape="task")
    src = add(auth, "list: [[buy milk]]")
    assert auth.patch(f"/api/items/{task['id']}", json={"title": "Buy oat milk"}).status_code == 200
    assert get(auth, src["id"])["raw_text"] == "list: [[Buy oat milk]]"


def test_no_rewrite_while_another_item_keeps_the_old_title(auth):
    add(auth, "Checklist")
    moving = add(auth, "Checklist", space="home")
    src = add(auth, "see [[Checklist]]")
    edit(auth, moving["id"], "Packing list")
    assert get(auth, src["id"])["raw_text"] == "see [[Checklist]]"


def test_a_rename_that_retitles_the_linker_follows_through(auth):
    """The link is the linking item's own first line, so its title changes and the links to *it*
    are rewritten in turn."""
    a = add(auth, "Alpha")
    b = add(auth, "[[Alpha]] notes")
    c = add(auth, "see [[Alpha notes]]")
    edit(auth, a["id"], "Beta")
    assert get(auth, b["id"])["raw_text"] == "[[Beta]] notes"
    assert get(auth, c["id"])["raw_text"] == "see [[Beta notes]]"


def test_a_nested_rewrite_is_not_overwritten_by_a_stale_read(auth):
    """Review finding: C links to both A and B, and B's title contains a link to A. Renaming A
    retitles B, which rewrites C; the outer loop must then work on C as it is now."""
    a = add(auth, "Alpha")
    add(auth, "[[Alpha]] plan\n\nbody")
    c = add(auth, "x\n\n[[Alpha plan]] and [[Alpha]]")
    edit(auth, a["id"], "Alpha2")
    assert get(auth, c["id"])["raw_text"] == "x\n\n[[Alpha2 plan]] and [[Alpha2]]"
    assert None not in get(auth, c["id"])["links"].values()


def test_no_rewrite_to_a_title_its_own_link_would_not_find(auth):
    a = add(auth, "Plain")
    src = add(auth, "see [[Plain]]")
    edit(auth, a["id"], "**# odd**")
    assert get(auth, src["id"])["raw_text"] == "see [[Plain]]"


def test_deleting_the_target_leaves_the_link_missing(auth):
    gone = add(auth, "Temporary")
    src = add(auth, "see [[Temporary]]")
    auth.delete(f"/api/items/{gone['id']}")
    assert get(auth, src["id"])["links"] == {"Temporary": None}


def test_suggest_and_resolve(auth):
    docker = add(auth, "Docker setup")
    add(auth, "Set up docker compose", space="home")
    me = add(auth, "Docker notes")
    got = auth.get("/api/links/suggest", params={"q": "dock", "exclude": me["id"]}).json()["items"]
    assert [i["title"] for i in got] == ["Docker setup", "Set up docker compose"]
    assert got[0] == {"id": docker["id"], "title": "Docker setup", "space": "work", "shape": "note"}
    assert auth.get("/api/links/resolve", params={"title": "docker SETUP"}).json() == {
        "id": docker["id"]
    }
    assert auth.get("/api/links/resolve", params={"title": "nothing"}).status_code == 404
    assert auth.get("/api/links/suggest", params={"q": "100%_"}).json()["items"] == []


def test_the_index_is_rebuilt_from_the_text(auth, settings):
    target = add(auth, "Target")
    src = add(auth, "to [[Target]]")
    conn = db.connect(settings.db_path)
    conn.execute("DELETE FROM item_links")
    conn.execute("DELETE FROM item_keys")
    conn.commit()
    assert reindex_links(conn) >= 2
    before = conn.execute("SELECT updated_at FROM items WHERE id = ?", (src["id"],)).fetchone()[0]
    conn.close()
    assert get(auth, src["id"])["links"] == {"Target": target["id"]}
    assert get(auth, src["id"])["updated_at"] == before  # an index write is not an edit


# --- phase B: [[space:name]] ---


def test_a_space_link_lists_the_item_under_that_space_not_in_it(auth):
    item = add(auth, "Console app\n\nalso [[space:Home]] and [[space:nowhere]]", shape="task")
    got = get(auth, item["id"])
    assert got["space_links"] == {"space:Home": "home", "space:nowhere": None}
    assert got["links"] == {}
    linked = auth.get("/api/spaces/home/linked").json()["items"]
    assert [i["id"] for i in linked] == [item["id"]]
    own = auth.get("/api/items", params={"space": "home"}).json()["items"]
    assert item["id"] not in [i["id"] for i in own]  # it keeps its one space
    # An item already in the space is its own, not "linked here".
    add(auth, "Kitchen\n\n[[space:home]]", space="home")
    assert len(auth.get("/api/spaces/home/linked").json()["items"]) == 1


def test_renaming_a_space_rewrites_its_links(auth):
    auth.post("/api/spaces", json={"name": "coding"})
    item = add(auth, "Console app\n\nsee [[space:coding]], keep `[[space:coding]]`")
    assert auth.patch("/api/spaces/coding", json={"name": "code"}).status_code == 200
    got = get(auth, item["id"])
    assert got["raw_text"] == "Console app\n\nsee [[space:code]], keep `[[space:coding]]`"
    assert got["space_links"] == {"space:code": "code"}
    assert [i["id"] for i in auth.get("/api/spaces/code/linked").json()["items"]] == [item["id"]]


def test_deleting_a_space_leaves_its_links_missing(auth):
    auth.post("/api/spaces", json={"name": "scratch"})
    item = add(auth, "see [[space:scratch]]")
    assert auth.delete("/api/spaces/scratch").status_code == 200
    assert get(auth, item["id"])["space_links"] == {"space:scratch": None}


def test_a_space_link_never_opens_an_item(auth):
    add(auth, "space:home")  # an item whose first line looks like one
    src = add(auth, "see [[space:home]]")
    assert get(auth, src["id"])["links"] == {}
    assert auth.get("/api/links/resolve", params={"title": "space:home"}).status_code == 404


def test_a_space_after_the_colon_is_the_same_space_link(auth):
    """Pre-deploy review: `[[space: home]]` rendered as a link but was not indexed as one."""
    item = add(auth, "see [[space: home]]")
    assert [i["id"] for i in auth.get("/api/spaces/home/linked").json()["items"]] == [item["id"]]
