"""Spaces: a user-managed list. Seeded once from TARTIB_SPACES, then edited here."""

from __future__ import annotations

import re
import sqlite3
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from tartib.auth import require_auth
from tartib.clock import utcnow_iso
from tartib.deps import get_db
from tartib.store import list_spaces, rewrite_space_links, space_policies

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,23}$")


def clean_name(raw: str) -> str:
    name = raw.strip().lower()
    if not NAME_RE.match(name):
        raise HTTPException(
            status_code=422,
            detail="space names are 1 to 24 characters: lowercase letters, digits, dashes",
        )
    return name


def seed_spaces(conn: sqlite3.Connection, names: tuple[str, ...] | list[str]) -> int:
    """Fill an empty table from the env list. No-op once the table has rows."""
    if conn.execute("SELECT COUNT(*) FROM spaces").fetchone()[0]:
        return 0
    now = utcnow_iso()
    rows = [(n, i, now) for i, n in enumerate(names) if NAME_RE.match(n)]
    conn.executemany("INSERT INTO spaces (name, position, created_at) VALUES (?, ?, ?)", rows)
    conn.commit()
    return len(rows)


class SpaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=64)


class PolicyBody(BaseModel):
    policy: Literal["auto", "ask", "file"]


@router.get("/spaces")
def get_spaces(conn: sqlite3.Connection = Depends(get_db)) -> dict:
    return {"spaces": list_spaces(conn), "policies": space_policies(conn)}


@router.put("/spaces/{name}/policy")
def set_policy(name: str, body: PolicyBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """How this space takes proposals: the global rule, always ask, or always file."""
    space = name.strip().lower()
    if space not in list_spaces(conn):
        raise HTTPException(status_code=404, detail="unknown space")
    conn.execute("UPDATE spaces SET policy = ? WHERE name = ?", (body.policy, space))
    conn.commit()
    return {"name": space, "policy": body.policy}


def add_space(conn: sqlite3.Connection, name: str) -> str:
    """Create a space and return its name. Shared so accepting a classifier's proposed space
    (slice 28) means exactly what the Spaces page means by creating one."""
    clean = clean_name(name)
    if clean in list_spaces(conn):
        raise HTTPException(status_code=409, detail="that space already exists")
    position = conn.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM spaces").fetchone()[0]
    conn.execute(
        "INSERT INTO spaces (name, position, created_at) VALUES (?, ?, ?)",
        (clean, position, utcnow_iso()),
    )
    conn.commit()
    return clean


@router.post("/spaces", status_code=201)
def create_space(body: SpaceBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    name = add_space(conn, body.name)
    return {"spaces": list_spaces(conn), "name": name}


@router.patch("/spaces/{name}")
def rename_space(name: str, body: SpaceBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Rename, carrying every item and the cached brief along."""
    old = name.strip().lower()
    new = clean_name(body.name)
    if old not in list_spaces(conn):
        raise HTTPException(status_code=404, detail="unknown space")
    if new != old and new in list_spaces(conn):
        raise HTTPException(status_code=409, detail="that space already exists")
    if new != old:
        conn.execute("UPDATE spaces SET name = ? WHERE name = ?", (new, old))
        conn.execute("UPDATE items SET space = ? WHERE space = ?", (new, old))
        conn.execute("UPDATE briefs SET space = ? WHERE space = ?", (new, old))
        rewrite_space_links(conn, old, new, list_spaces(conn))
        conn.commit()
    return {"spaces": list_spaces(conn), "name": new}


@router.delete("/spaces/{name}")
def delete_space(name: str, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Only an empty space can go. Move or delete its items first."""
    space = name.strip().lower()
    if space not in list_spaces(conn):
        raise HTTPException(status_code=404, detail="unknown space")
    count = conn.execute("SELECT COUNT(*) FROM items WHERE space = ?", (space,)).fetchone()[0]
    if count:
        raise HTTPException(
            status_code=409, detail=f"{space} still has {count} item{'s' if count != 1 else ''}"
        )
    conn.execute("DELETE FROM spaces WHERE name = ?", (space,))
    conn.execute("DELETE FROM briefs WHERE space = ?", (space,))
    conn.commit()
    return {"spaces": list_spaces(conn)}
