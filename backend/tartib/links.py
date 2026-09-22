"""Links between items (slice 33): what an item's `[[…]]` point at, what points at it, and the
editor's picker. The index itself is kept by the store (`index_links`, `update_fields`)."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, Depends, HTTPException, Query

from tartib.auth import require_auth
from tartib.deps import get_db
from tartib.store import (
    LINK,
    SPACE_LINK,
    link_key,
    list_spaces,
    resolve_link,
    serialize_item,
    space_of,
)

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

SUGGEST = 8
LINKED_FROM = 50


def link_view(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    """`links`: each `[[…]]` in the text, as written, to the id it opens or null when nothing
    answers to it -- keyed as written so the client needs no copy of the key rule.
    `linked_from`: the items whose links open this one. With two items sharing a first line only
    the one that wins the link is linked from."""
    written = [m.group(2) for m in LINK.finditer(row["raw_text"] or "") if m.group(2)]
    spaces = set(list_spaces(conn))
    links: dict = {}
    space_links: dict = {}
    for w in written:
        key = link_key(w)
        name = space_of(key)
        if name is not None:
            space_links[w] = name if name in spaces else None
        else:
            links[w] = resolve_link(conn, key) if key else None
    key = conn.execute("SELECT key FROM item_keys WHERE item_id = ?", (row["id"],)).fetchone()
    linked_from: list = []
    if key and key["key"] and resolve_link(conn, key["key"]) == row["id"]:
        linked_from = conn.execute(
            "SELECT i.* FROM item_links l JOIN items i ON i.id = l.source_id"
            " WHERE l.target = ? AND l.source_id != ? ORDER BY i.updated_at DESC LIMIT ?",
            (key["key"], row["id"], LINKED_FROM),
        ).fetchall()
    return {
        "links": links,
        "space_links": space_links,
        "linked_from": [serialize_item(r) for r in linked_from],
    }


@router.get("/links/suggest")
def suggest(
    q: str = Query(default="", max_length=200),
    exclude: int | None = None,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Items whose first line contains `q`, most recently touched first, for the `[[` picker.
    Starts-with matches come first: typing the start of a title is the usual way in."""
    needle = " ".join(q.split()).casefold()
    like = "%" + needle.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
    rows = conn.execute(
        "SELECT i.id, i.space, i.shape, k.title, k.key FROM item_keys k"
        " JOIN items i ON i.id = k.item_id"
        " WHERE k.key != '' AND k.key LIKE ? ESCAPE '\\' AND i.id IS NOT ?"
        " ORDER BY substr(k.key, 1, length(?)) = ? DESC, i.updated_at DESC LIMIT ?",
        (like, exclude, needle, needle, SUGGEST),
    ).fetchall()
    return {
        "items": [
            {"id": r["id"], "title": r["title"], "space": r["space"], "shape": r["shape"]}
            for r in rows
        ]
    }


@router.get("/spaces/{name}/linked")
def linked_to_space(name: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Items in other spaces whose text links here with `[[space:name]]`. Listed apart from the
    space's own items and never counted among them: the item still has one space (phase B)."""
    space = name.strip().lower()
    rows = conn.execute(
        "SELECT i.* FROM item_links l JOIN items i ON i.id = l.source_id"
        " WHERE l.target = ? AND i.space IS NOT ? ORDER BY i.updated_at DESC LIMIT ?",
        (SPACE_LINK + space, space, LINKED_FROM),
    ).fetchall()
    return {"items": [serialize_item(r) for r in rows]}


@router.get("/links/resolve")
def resolve(
    title: str = Query(min_length=1, max_length=500), conn: sqlite3.Connection = Depends(get_db)
) -> dict:
    """Where `[[title]]` goes, for a link drawn where the item's own map is not at hand -- an Ask
    answer, a brief."""
    found = resolve_link(conn, link_key(title))
    if found is None:
        raise HTTPException(status_code=404, detail="no item has that first line")
    return {"id": found}
