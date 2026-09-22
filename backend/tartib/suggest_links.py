"""Suggest links for items already filed (slice 34).

    python -m tartib.suggest_links --space infra              up to 20 items, stored
    python -m tartib.suggest_links --space infra --limit 5
    python -m tartib.suggest_links --space infra --dry-run    print only, store nothing

For each filed note or task in the space, most recently touched first, the classifier is shown
what a new capture of that text would be shown -- the similar items, minus the item itself --
and asked for links whatever TARTIB_LINK_PROPOSALS says: running this is the asking. An item that
gets any goes back to Needs attention as `relink`, with each as a chip; approving files it back
exactly as it was, with `Related: [[…]]` for the kept ones. One suggestion per pair, and a pair
suggested before -- kept, skipped or pending -- or already linked is never suggested again.
Safe with the server up.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import sqlite3
import sys
import time
from dataclasses import dataclass, field

from tartib import db
from tartib.classify import ClassifyError, Context, PromptShape, classify
from tartib.clock import utcnow, utcnow_iso
from tartib.config import Settings, load_settings
from tartib.store import (
    CANDIDATES,
    classifier_examples,
    classify_context,
    house_rules,
    link_title,
    list_spaces,
    pair_known,
    record_call,
    save_quota,
    similar_items,
    suggest,
)

CONCURRENCY = 3
DEFAULT_LIMIT = 20


@dataclass
class Report:
    items: int = 0
    suggested: int = 0  # items sent back with at least one link
    links: int = 0
    failed: int = 0
    lines: list[str] = field(default_factory=list)


def text_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode()).hexdigest()[:16]


def select_items(conn: sqlite3.Connection, space: str, limit: int) -> list[sqlite3.Row]:
    """Filed notes and tasks in the space, most recently touched first, `limit` of them.

    Only filed: an item already waiting has its own question to answer first. Not a task whose
    reminder has yet to fire -- the reminder loop reads filed items only, so a reminder due while
    it waited would be written off. Not an item asked about before whose text has not changed
    since (`link_asks`): it would cost a call to hear the same answer."""
    rows = conn.execute(
        "SELECT i.*, a.text_hash AS asked_hash FROM items i"
        " LEFT JOIN link_asks a ON a.item_id = i.id"
        " WHERE i.stage = 'filed' AND i.space = ? AND i.shape IN ('note', 'task')"
        " AND NOT (i.remind_at IS NOT NULL AND i.reminded_at IS NULL)"
        " ORDER BY i.updated_at DESC, i.id DESC",
        (space,),
    ).fetchall()
    return [r for r in rows if r["asked_hash"] != text_hash(r["raw_text"])][:limit]


def candidates_for(conn: sqlite3.Connection, row: sqlite3.Row) -> tuple[tuple[str, object], ...]:
    """What a new capture of this text would be shown, without the item itself, relabelled."""
    rows = [r for _, r in similar_items(conn, row["raw_text"], limit=CANDIDATES + 1)]
    rows = [r for r in rows if r["id"] != row["id"]][:CANDIDATES]
    return tuple((f"i{n}", r) for n, r in enumerate(rows, 1))


async def run(settings: Settings, space: str, limit: int, dry_run: bool) -> Report:
    conn = db.connect(settings.db_path)
    report = Report()
    try:
        if space not in list_spaces(conn):
            raise SystemExit(f"unknown space {space!r}")
        items = select_items(conn, space, limit)
        report.items = len(items)
        base = {
            "zone": settings.zone,
            "spaces": tuple(list_spaces(conn)),
            "codex": settings.codex(),
            "existing": classify_context(conn),
            "house_rules": house_rules(conn),
            "examples": classifier_examples(conn, threshold=settings.autofile_confidence)[0],
            "links": True,
        }
        gate = asyncio.Semaphore(CONCURRENCY)

        async def one(row):
            candidates = candidates_for(conn, row)
            if not candidates:
                return row, [], None, None
            seen: list = []
            started = time.monotonic()
            context = Context(now=utcnow().astimezone(settings.zone), candidates=candidates, **base)
            async with gate:
                try:
                    proposals = await classify(
                        row["raw_text"],
                        context,
                        on_usage=lambda u, q, sh: seen.append((u, q, sh)),
                    )
                    failure = None
                except ClassifyError as e:
                    proposals, failure = [], e
            ms = int((time.monotonic() - started) * 1000)
            p = next((x for x in proposals if x.shape != "question"), None)
            related = [int(i) for i in (p.related if p else [])]
            return row, related, failure, (seen[0] if seen else None, ms)

        results = await asyncio.gather(*(one(r) for r in items))
        chosen: set[tuple[int, int]] = set()
        for row, related, failure, call in results:
            name = link_title(row["raw_text"])[:60]
            if call is not None and not dry_run:
                seen, ms = call
                usage, quota, shape = seen or (None, None, None)
                save_quota(conn, quota)
                record_call(
                    conn,
                    kind="relink",
                    model=settings.ai_model,
                    usage=usage,
                    duration_ms=ms,
                    failure=str(failure) if failure else None,
                    shape=shape or PromptShape(links=True),
                )
            if failure is not None:
                report.failed += 1
                report.lines.append(f"#{row['id']} {name!r}: failed: {str(failure)[:120]}")
                continue
            if not dry_run:
                # Asked, whatever the answer: the same text is not asked about again.
                conn.execute(
                    "INSERT INTO link_asks (item_id, text_hash, asked_at) VALUES (?, ?, ?)"
                    " ON CONFLICT(item_id) DO UPDATE SET text_hash = excluded.text_hash,"
                    " asked_at = excluded.asked_at",
                    (row["id"], text_hash(row["raw_text"]), utcnow_iso()),
                )
                conn.commit()
            # One per pair: this run's own choices count too, in either direction.
            keep = [
                t
                for t in related
                if t != row["id"]
                and (row["id"], t) not in chosen
                and (t, row["id"]) not in chosen
                and not pair_known(conn, row["id"], t)
            ]
            for t in keep:
                chosen.add((row["id"], t))
            if not keep:
                report.lines.append(f"#{row['id']} {name!r}: nothing")
                continue
            if not dry_run:
                keep = suggest(conn, row["id"], keep)
                conn.commit()
                if not keep:
                    report.lines.append(f"#{row['id']} {name!r}: changed meanwhile, left alone")
                    continue
            targets = conn.execute(
                f"SELECT id, raw_text FROM items WHERE id IN ({', '.join('?' * len(keep))})", keep
            ).fetchall()
            names = {t["id"]: link_title(t["raw_text"])[:50] for t in targets}
            report.lines.append(
                f"#{row['id']} {name!r} -> " + ", ".join(f"#{t} {names.get(t)!r}" for t in keep)
            )
            report.suggested += 1
            report.links += len(keep)
    finally:
        conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m tartib.suggest_links")
    parser.add_argument("--space", required=True, help="the space to go through")
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT, help="items, one call each")
    parser.add_argument("--dry-run", action="store_true", help="print only; store nothing")
    args = parser.parse_args(argv)
    if args.limit < 1:
        parser.error("--limit must be at least 1")
    settings = load_settings()
    if not settings.ai_enabled:
        print("the classifier is off (TARTIB_AI_COMMAND)", file=sys.stderr)
        return 2
    report = asyncio.run(run(settings, args.space.strip().lower(), args.limit, args.dry_run))
    for line in report.lines:
        print(line)
    verb = "would send back" if args.dry_run else "sent back"
    print(
        f"\n{report.items} items, {verb} {report.suggested} with {report.links} links,"
        f" {report.failed} failed" + (" (dry run: nothing stored)" if args.dry_run else "")
    )
    return 1 if report.failed and not report.suggested else 0


if __name__ == "__main__":
    sys.exit(main())
