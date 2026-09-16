"""FastAPI dependencies."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

from fastapi import Request

from tartib import db
from tartib.config import Settings


def get_settings(request: Request) -> Settings:
    return request.app.state.settings


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    conn = db.connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()
