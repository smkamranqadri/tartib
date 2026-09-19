"""One-off: run the classifier again over existing captures.

    python -m tartib.reclassify --all          every capture
    python -m tartib.reclassify --attention    only captures with an item waiting, or that errored
    python -m tartib.reclassify --all --dry-run

Items are rebuilt from their captures. Where a capture still yields exactly one task, its
`starred` and `status` carry over. Manual edits to space, title, or dates do not. Safe to run
while the server is up: the server only picks up pending captures at startup, and this
command processes them itself, so do not restart the server mid-run.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from dataclasses import dataclass

from tartib import db
from tartib.config import Settings, load_settings
from tartib.runner import Runner


@dataclass
class Report:
    selected: int = 0
    reset: int = 0
    carried: int = 0
    done: int = 0
    errored: int = 0
    items_filed: int = 0
    items_attention: int = 0
    answered: int = 0


def select_ids(conn, scope: str) -> list[int]:
    # A capture filed by hand never goes to the classifier: it would overwrite what was chosen.
    if scope == "all":
        rows = conn.execute("SELECT id FROM captures WHERE direct = 0 ORDER BY id").fetchall()
    else:
        rows = conn.execute(
            "SELECT DISTINCT c.id FROM captures c LEFT JOIN items i ON i.capture_id = c.id"
            " WHERE c.direct = 0 AND (c.status = 'error' OR i.stage = 'attention') ORDER BY c.id"
        ).fetchall()
    return [r["id"] for r in rows]


def snapshot_flags(conn, ids: list[int]) -> dict[int, tuple[int, str]]:
    """starred/status of captures that currently have exactly one task item."""
    out: dict[int, tuple[int, str]] = {}
    for cid in ids:
        rows = conn.execute(
            "SELECT shape, starred, status FROM items WHERE capture_id = ?", (cid,)
        ).fetchall()
        if len(rows) == 1 and rows[0]["shape"] == "task":
            out[cid] = (rows[0]["starred"], rows[0]["status"])
    return out


def reset(conn, ids: list[int]) -> int:
    n = 0
    for cid in ids:
        conn.execute("DELETE FROM items WHERE capture_id = ?", (cid,))
        conn.execute(
            "UPDATE captures SET status = 'pending', error = NULL, answer_json = NULL,"
            " classified_at = NULL WHERE id = ?",
            (cid,),
        )
        n += 1
    conn.commit()
    return n


def carry_over(conn, flags: dict[int, tuple[int, str]]) -> int:
    n = 0
    for cid, (starred, status) in flags.items():
        rows = conn.execute("SELECT id, shape FROM items WHERE capture_id = ?", (cid,)).fetchall()
        if len(rows) == 1 and rows[0]["shape"] == "task" and (starred or status == "done"):
            conn.execute(
                "UPDATE items SET starred = ?, status = ? WHERE id = ?",
                (starred, status, rows[0]["id"]),
            )
            n += 1
    conn.commit()
    return n


async def reclassify(settings: Settings, scope: str, dry_run: bool = False) -> Report:
    report = Report()
    conn = db.connect(settings.db_path)
    try:
        db.migrate(conn)
        ids = select_ids(conn, scope)
        report.selected = len(ids)
        flags = snapshot_flags(conn, ids)
        if dry_run or not ids:
            return report
        report.reset = reset(conn, ids)
    finally:
        conn.close()

    runner = Runner(settings, retry=False)
    await runner.start()  # picks up everything pending
    await runner.queue.join()
    await runner.stop()

    conn = db.connect(settings.db_path)
    try:
        report.carried = carry_over(conn, flags)
        placeholders = ", ".join("?" * len(ids))
        row = conn.execute(
            f"SELECT SUM(status = 'done'), SUM(status = 'error'), SUM(answer_json IS NOT NULL)"
            f" FROM captures WHERE id IN ({placeholders})",
            ids,
        ).fetchone()
        report.done, report.errored, report.answered = (int(x or 0) for x in row)
        row = conn.execute(
            f"SELECT SUM(stage = 'filed'), SUM(stage = 'attention') FROM items"
            f" WHERE capture_id IN ({placeholders})",
            ids,
        ).fetchone()
        report.items_filed, report.items_attention = (int(x or 0) for x in row)
    finally:
        conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--all", action="store_true", help="every capture")
    scope.add_argument("--attention", action="store_true", help="only waiting or errored captures")
    parser.add_argument("--dry-run", action="store_true", help="report what would be reset")
    args = parser.parse_args(argv)
    settings = load_settings()
    if not settings.ai_enabled:
        print("AI is off (TARTIB_AI_COMMAND); nothing to do.", file=sys.stderr)
        return 2
    report = asyncio.run(reclassify(settings, "all" if args.all else "attention", args.dry_run))
    if args.dry_run:
        print(f"would reset {report.selected} captures")
        return 0
    print(
        f"reclassified {report.reset} captures: {report.done} done, {report.errored} errored,"
        f" {report.answered} answered; items: {report.items_filed} filed,"
        f" {report.items_attention} need attention; flags carried over on {report.carried}"
    )
    return 0 if report.errored == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
