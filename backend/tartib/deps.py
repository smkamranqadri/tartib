"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from tartib import db
from tartib.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def push_ready(request: Request) -> bool:
    """Whether this install can actually deliver a push. Keys alone are not enough: an unusable
    private key leaves the loop off, and the UI must not offer to switch on something that can
    never fire."""
    settings: Settings = request.app.state.settings
    return bool(getattr(request.app.state, "push_ready", settings.push_enabled))


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
