"""Row helpers and the shared write paths, so the runner and the API file items the same way."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from tartib.clock import utcnow, utcnow_iso, utcnow_ms_iso

FILING_FIELDS = ("shape", "space", "title", "due", "remind_at")
EDITABLE_FIELDS = FILING_FIELDS + ("starred", "status", "text")


class SpaceError(ValueError):
    """A space that is not configured, or a missing space where one is required."""


def serialize_item(row: sqlite3.Row) -> dict:
    item = dict(row)
    item["starred"] = bool(item["starred"])
    raw = item.pop("proposal_json", None)
    item["proposal"] = json.loads(raw) if raw else None
    return item


def serialize_capture(conn: sqlite3.Connection, row: sqlite3.Row) -> dict:
    cap = dict(row)
    raw = cap.pop("answer_json", None)
    cap["answer"] = json.loads(raw) if raw else None
    rows = conn.execute(
        "SELECT * FROM items WHERE capture_id = ? ORDER BY id", (cap["id"],)
    ).fetchall()
    cap["items"] = [serialize_item(r) for r in rows]
    return cap


def to_db_value(field: str, value: object) -> object:
    if value is None:
        return None
    if field == "due" and isinstance(value, date):
        return value.isoformat()
    if field == "remind_at" and isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return value.astimezone(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    if field == "starred":
        return 1 if value else 0
    return value


def check_space(space: object, allowed: Sequence[str]) -> str | None:
    if space is None:
        return None
    s = str(space).strip().lower()
    if not s:
        return None
    if s not in allowed:
        raise SpaceError(f"unknown space {s!r}; configured: {', '.join(allowed)}")
    return s


STALE_DAYS = 14  # an open task nobody has touched for this long is waiting, whatever its stage


def stale_cutoff() -> str:
    return (utcnow() - timedelta(days=STALE_DAYS)).isoformat().replace("+00:00", "Z")


def waiting_counts(conn: sqlite3.Connection) -> tuple[int, int]:
    """(undecided, stale) -- the two halves of what the app calls waiting.

    The nav badge has always summed both (`App.tsx`), and the Inbox has always shown both. The
    digest counted only the first half, so it undercounted every morning. One owner for the
    definition, because two copies of "stale" is how they came to disagree.
    """
    undecided = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE stage = 'attention'"
    ).fetchone()["n"]
    stale = conn.execute(
        "SELECT COUNT(*) AS n FROM items WHERE stage = 'filed' AND shape = 'task'"
        " AND status = 'open' AND updated_at < ?",
        (stale_cutoff(),),
    ).fetchone()["n"]
    return int(undecided or 0), int(stale or 0)


EXAMPLE_FIELDS = ("shape", "space", "title", "due")
EXAMPLES_MAX = 5  # in the prompt
EXAMPLES_SCAN = 120  # most recent filed items to look through


@dataclass(frozen=True)
class Example:
    """One filed item as something to learn from."""

    text: str
    was: dict  # what the classifier proposed, for the fields that differ
    became: dict  # what it actually became
    corrected: bool  # False means it was accepted untouched -- padding, the weaker signal


def _correction(proposal: dict, row: sqlite3.Row) -> dict:
    """The fields the person actually changed.

    **Only a field the classifier itself proposed may count.** When it proposed no space, the
    filing code supplies one -- `approve` falls back to the item's own space -- and reading that
    as a correction teaches the classifier from our own fallback rather than from the person.
    """
    out = {}
    for field in EXAMPLE_FIELDS:
        proposed = proposal.get(field)
        if proposed is None or proposed == "":
            continue  # not proposed: whatever it became came from somewhere else
        actual = row[field]
        if actual is not None and str(actual) != str(proposed):
            out[field] = (proposed, actual)
    return out


def classifier_examples(
    conn: sqlite3.Connection, limit: int = EXAMPLES_MAX, threshold: float = 0.85
) -> tuple[tuple[Example, ...], int]:
    """Examples for the prompt, corrections first. Returns (examples, how many are real).

    Padding with items accepted untouched is the fallback and never the default: those are the
    classifier's own output, so leaning on them teaches it its own habits back. Only items it
    was confident about are worth padding with.
    """
    rows = conn.execute(
        "SELECT * FROM items WHERE stage = 'filed' AND proposal_json IS NOT NULL"
        " ORDER BY id DESC LIMIT ?",
        (EXAMPLES_SCAN,),
    ).fetchall()
    corrections: list[Example] = []
    accepted: list[Example] = []
    for row in rows:
        try:
            proposal = json.loads(row["proposal_json"]) or {}
        except ValueError:
            continue
        text = " ".join((row["raw_text"] or "").split())[:120]
        if not text:
            continue
        changed = _correction(proposal, row)
        if changed:
            corrections.append(
                Example(
                    text=text,
                    was={f: v[0] for f, v in changed.items()},
                    became={f: v[1] for f, v in changed.items()},
                    corrected=True,
                )
            )
        elif float(proposal.get("confidence") or 0) >= threshold:
            accepted.append(
                Example(
                    text=text,
                    was={},
                    became={f: row[f] for f in EXAMPLE_FIELDS if row[f] is not None},
                    corrected=False,
                )
            )
    out = corrections[:limit]
    if len(out) < limit:
        out += accepted[: limit - len(out)]
    return tuple(out), len(corrections)


def list_spaces(conn: sqlite3.Connection) -> list[str]:
    return [r["name"] for r in conn.execute("SELECT name FROM spaces ORDER BY position, name")]


def space_policies(conn: sqlite3.Connection) -> dict[str, str]:
    return {r["name"]: r["policy"] for r in conn.execute("SELECT name, policy FROM spaces")}


CONTEXT_PER_SPACE = 5  # most recent items shown per space in the classifier's context
CONTEXT_EXCERPT = 60  # characters of a note shown there; a task shows its title instead


def item_header(row: sqlite3.Row) -> str:
    """The one line that identifies an item to the AI.

    Both prompts use it: ask puts the item's text and thoughts underneath, classify shows it
    alone as context. One format in one place, so the two prompts cannot drift apart about what
    an item looks like -- which is the whole of the backlog's "shared rules" entry that mattered.
    """
    space = row["space"] or "(none)"
    head = f"[id {row['id']}] {row['created_at'][:10]} · space: {space} · {row['shape']}"
    if row["shape"] == "task":
        head += f": {row['title'] or ''}"
        if row["due"]:
            head += f" · due {row['due']}"
        head += f" · {row['status']}"
    return head


def context_line(row: sqlite3.Row) -> str:
    """One item as the classifier sees it: its shared header, plus the start of a note's text,
    since a note's header has no content in it."""
    line = item_header(row)
    if row["shape"] == "task":
        return line
    first = " ".join((row["raw_text"] or "").split())
    if not first:
        return line
    if len(first) > CONTEXT_EXCERPT:
        first = first[:CONTEXT_EXCERPT].rstrip() + "\u2026"
    return f"{line}: {first}"


@dataclass(frozen=True)
class SpaceContext:
    """One space as the classifier sees it."""

    name: str
    open_tasks: int
    notes: int
    recent: tuple[str, ...]  # item_header lines, most recent first


def classify_context(
    conn: sqlite3.Connection, per_space: int = CONTEXT_PER_SPACE
) -> tuple[SpaceContext, ...]:
    """What already exists, for the classifier: every configured space with its counts and its
    most recent items.

    Built here so there is one source of truth for what the classifier is shown. Filed items
    only -- something sitting in attention is a guess nobody has confirmed, and showing guesses
    as examples of what lives in a space teaches the classifier its own mistakes.

    A task is its header, which carries its title. A note's header carries no content at all --
    space, shape and date -- so notes get CONTEXT_EXCERPT characters of their first line too,
    or the block would say nothing about the half of the database that is notes.

    Nothing longer: this rides on every capture, and captures queue serially.
    """
    counts = {
        r["space"]: r
        for r in conn.execute(
            """
            SELECT space,
                   SUM(shape = 'task' AND status = 'open') AS open_tasks,
                   SUM(shape = 'note') AS notes
            FROM items WHERE stage = 'filed' GROUP BY space
            """
        ).fetchall()
    }
    out = []
    for name in list_spaces(conn):
        row = counts.get(name)
        recent = conn.execute(
            "SELECT * FROM items WHERE space = ? AND stage = 'filed'"
            " ORDER BY id DESC LIMIT ?",
            (name, per_space),
        ).fetchall()
        out.append(
            SpaceContext(
                name=name,
                open_tasks=int(row["open_tasks"] or 0) if row else 0,
                notes=int(row["notes"] or 0) if row else 0,
                recent=tuple(context_line(r) for r in recent),
            )
        )
    return tuple(out)


def should_file(
    space: str | None, confidence: float, threshold: float, policies: dict[str, str]
) -> bool:
    """Whether a proposal files itself. No space never files; otherwise the space's policy
    decides, and `auto` falls back to the global confidence threshold."""
    if space is None:
        return False
    policy = policies.get(space, "auto")
    if policy == "ask":
        return False
    if policy == "file":
        return True
    return confidence >= threshold


def _clean(fields: dict, allowed: Sequence[str]) -> dict:
    values = {k: to_db_value(k, v) for k, v in fields.items() if k in EDITABLE_FIELDS}
    if "text" in values:
        text = str(values.pop("text") or "").strip()
        if text:
            values["raw_text"] = text
    if "space" in values:
        values["space"] = check_space(values["space"], allowed)
    if values.get("shape") == "note":
        values.update(title=None, due=None, remind_at=None)
    return values


def reconcile_spaces(conn: sqlite3.Connection, allowed: Sequence[str]) -> int:
    """Items whose space is no longer configured go back to Needs Attention with no space.

    Runs at startup so removing a space from TARTIB_SPACES never leaves filed items the UI
    cannot select or filter. Returns how many items moved."""
    placeholders = ", ".join("?" * len(allowed))
    cur = conn.execute(
        f"UPDATE items SET space = NULL, stage = 'attention'"
        f" WHERE space IS NOT NULL AND space NOT IN ({placeholders})",
        list(allowed),
    )
    conn.commit()
    return cur.rowcount


HOUSE_RULES_KEY = "classifier_house_rules"
HOUSE_RULES_MAX = 2000  # characters; this rides on every capture, like the context block


def house_rules(conn: sqlite3.Connection) -> str:
    """The owner's own filing rules, appended to the shipped classifier prompt.

    Appended, never a replacement: the JSON contract, the field definitions and the schema stay
    in code where no saved edit can reach them. A bad house rule can give bad advice; it cannot
    stop every capture from filing.
    """
    return (get_state(conn, HOUSE_RULES_KEY) or "").strip()


def set_house_rules(conn: sqlite3.Connection, text: str) -> str:
    """Store them, trimmed to HOUSE_RULES_MAX. Empty clears back to the shipped prompt."""
    cleaned = (text or "").strip()[:HOUSE_RULES_MAX]
    set_state(conn, HOUSE_RULES_KEY, cleaned)
    return cleaned


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    """`app_state` is the small key/value table migration 0005 added. It holds whatever has to
    outlive a restart and does not belong to an item: the digest's date, the login counters."""
    row = conn.execute("SELECT value FROM app_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT INTO app_state (key, value) VALUES (?, ?)"
        " ON CONFLICT (key) DO UPDATE SET value = excluded.value",
        (key, value),
    )
    conn.commit()


def clear_state(conn: sqlite3.Connection, *keys: str) -> None:
    conn.executemany("DELETE FROM app_state WHERE key = ?", [(k,) for k in keys])
    conn.commit()


def create_capture(
    conn: sqlite3.Connection, text: str, source: str, client_id: str | None = None
) -> int:
    cur = conn.execute(
        "INSERT INTO captures (raw_text, source, created_at, client_id) VALUES (?, ?, ?, ?)",
        (text, source, utcnow_iso(), client_id),
    )
    conn.commit()
    return int(cur.lastrowid or 0)


def capture_by_client_id(conn: sqlite3.Connection, client_id: str) -> int | None:
    """The capture this browser already sent under that id, if it arrived. What makes a queued
    capture safe to retry: the row is found instead of a second one being made."""
    row = conn.execute("SELECT id FROM captures WHERE client_id = ?", (client_id,)).fetchone()
    return int(row["id"]) if row else None


def insert_item(
    conn: sqlite3.Connection,
    *,
    capture_id: int,
    raw_text: str,
    created_at: str,
    fields: dict,
    stage: str,
    allowed: Sequence[str],
    proposal_json: str | None = None,
    proposal_error: str | None = None,
) -> int:
    values = _clean(fields, allowed)
    if stage == "filed" and not values.get("space"):
        raise SpaceError("a space is required to file an item")
    cols = [
        "capture_id",
        "raw_text",
        "created_at",
        "stage",
        "proposal_json",
        "proposal_error",
        "classified_at",
        *values.keys(),
    ]
    params = [
        capture_id,
        raw_text,
        created_at,
        stage,
        proposal_json,
        proposal_error,
        utcnow_iso(),
        *values.values(),
    ]
    cur = conn.execute(
        f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params
    )
    return int(cur.lastrowid or 0)


def update_fields(
    conn: sqlite3.Connection, item_id: int, fields: dict, allowed: Sequence[str]
) -> None:
    """Apply editable fields. Raises SpaceError for a bad space; the DB rejects filed + null."""
    values = _clean(fields, allowed)
    if not values:
        return
    if "remind_at" in values:
        # Moving a reminder re-arms it; without this a reminder that fired could never fire
        # again. It has to be a real *change*: the editor resends `remind_at` on every save,
        # so clearing on presence alone would re-fire the same reminder after a title edit.
        # The touch trigger skips writes that change `reminded_at`, so this edit -- a real
        # one, made by a person -- sets `updated_at` itself.
        row = conn.execute("SELECT remind_at FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is not None and row["remind_at"] != values["remind_at"]:
            values["reminded_at"] = None
            values["updated_at"] = utcnow_ms_iso()
    assignments = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", (*values.values(), item_id))


def file_item(
    conn: sqlite3.Connection,
    item_id: int,
    fields: dict,
    allowed: Sequence[str],
    *,
    proposal_json: str | None = None,
) -> None:
    """Move an item to `filed` with the given fields. A space is required."""
    values = _clean(fields, allowed)
    if not values.get("space"):
        raise SpaceError("a space is required to file an item")
    update_fields(conn, item_id, values, allowed)
    sets = ["stage = 'filed'", "proposal_error = NULL", "classified_at = ?"]
    params: list[object] = [utcnow_iso()]
    if proposal_json is not None:
        sets.append("proposal_json = ?")
        params.append(proposal_json)
    params.append(item_id)
    conn.execute(f"UPDATE items SET {', '.join(sets)} WHERE id = ?", params)
    conn.commit()


def thoughts_for(conn: sqlite3.Connection, item_ids: Sequence[int]) -> dict[int, list[sqlite3.Row]]:
    """Each item's thought entries, oldest first."""
    if not item_ids:
        return {}
    marks = ", ".join("?" * len(item_ids))
    out: dict[int, list[sqlite3.Row]] = {}
    for r in conn.execute(
        f"SELECT * FROM item_thoughts WHERE item_id IN ({marks}) ORDER BY id", list(item_ids)
    ):
        out.setdefault(r["item_id"], []).append(r)
    return out


def items_by_thoughts(
    conn: sqlite3.Connection,
    match: str,
    where: Sequence[str],
    params: Sequence[object],
    exclude: Sequence[int],
    limit: int,
) -> list[sqlite3.Row]:
    """Items whose thoughts match an FTS5 query, newest first, under the same filters -- the
    ones their own text did not already bring up."""
    sql = (
        "SELECT items.* FROM items WHERE items.id IN (SELECT t.item_id FROM thoughts_fts"
        " JOIN item_thoughts t ON t.id = thoughts_fts.rowid WHERE thoughts_fts MATCH ?)"
    )
    args: list[object] = [match]
    for clause in where:
        sql += f" AND {clause}"
    args += list(params)
    if exclude:
        sql += f" AND items.id NOT IN ({', '.join('?' * len(exclude))})"
        args += list(exclude)
    sql += " ORDER BY items.id DESC LIMIT ?"
    args.append(limit)
    return conn.execute(sql, args).fetchall()
