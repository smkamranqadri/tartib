"""SQLite access: one connection per request, numbered SQL migrations applied at startup."""

from __future__ import annotations

import sqlite3
from pathlib import Path

MIGRATIONS = Path(__file__).parent / "migrations"


def connect(path: str) -> sqlite3.Connection:
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def migrate(conn: sqlite3.Connection) -> int:
    """Apply every migration newer than the recorded version. Returns the final version."""
    conn.execute("CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL)")
    row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
    current = row["v"] or 0
    for path in sorted(MIGRATIONS.glob("*.sql")):
        version = int(path.name.split("_", 1)[0])
        if version <= current:
            continue
        conn.executescript(path.read_text())
        conn.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
        conn.commit()
        current = version
    return current
