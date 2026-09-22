"""Row helpers and the shared write paths, so the runner and the API file items the same way."""

from __future__ import annotations

import json
import re
import sqlite3
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

from tartib.clock import utcnow, utcnow_iso, utcnow_ms_iso

FILING_FIELDS = ("shape", "space", "title", "due", "remind_at")
EDITABLE_FIELDS = FILING_FIELDS + ("starred", "status", "text")


# --- the title is the text's first line (slice 31) ---
#
# `title` is still a column, and everything that names an item reads it -- rows, reminders,
# sessions, Ask's item header, the classifier's context -- but it is **derived**: for a task it
# is always the flattened first line of `raw_text`, set here on every write, never stored apart
# from the text. A note keeps `title` null; what names a note is its first line too, read
# straight from the text. The AI's task title reaches the text as line one (rule 1, amended
# 2026-09-22); the capture's own text is never touched.

_LEADERS = re.compile(r"^\s*(?:#{1,6}\s+|>\s*|(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?)*")
_INLINE = re.compile(r"(\*\*|__|~~|`)")


def title_of(text: str | None) -> str | None:
    """The first non-empty line, with its markdown taken off. None for empty text."""
    for line in (text or "").split("\n"):
        flat = _INLINE.sub("", _LEADERS.sub("", line)).strip()
        if flat:
            return flat
    return None


def same_title(a: str | None, b: str | None) -> bool:
    """Whether two lines name the same thing: markdown off, case ignored. "Call the dentist" and
    "call the dentist" are one title, and adding the first above the second would repeat it."""
    fa, fb = title_of(a), title_of(b)
    return (fa or "").casefold() == (fb or "").casefold()


def retitle(text: str, title: str | None, *, replace: bool = False) -> str:
    """`text` with `title` as its first line, or unchanged when it already is.

    `replace` is an edit of the title: for a task, line one *is* the title, so that line is
    rewritten. Without it -- a task being filed -- the title goes above, a blank line between,
    so nothing captured is overwritten."""
    new = (title or "").strip()
    if not new or same_title(text, new):
        return text
    if replace and text.strip():
        lines = text.split("\n")
        at = next(i for i, line in enumerate(lines) if line.strip())
        lines[at] = new
        return "\n".join(lines)
    return f"{new}\n\n{text}" if text.strip() else new


# --- links: `[[Title]]` in the text (slice 33) ---
#
# A link names its target's first line. The key is that line flattened by `title_of` and
# case-folded, which is `same_title`'s notion of equal, so `[[call the dentist]]` finds "Call the
# dentist". Two items with one key: the most recently touched wins. Code is not text: a `[[…]]`
# inside a fence or a code span is not a link, as the renderer does not draw it as one (indented
# code blocks are the known gap).

LINK = re.compile(r"(```.*?(?:```|\Z)|~~~.*?(?:~~~|\Z)|`[^`\n]*`)|\[\[([^\[\]\n]+?)\]\]", re.S)
MAX_REWRITE_DEPTH = 3


_BRACKETS = re.compile(r"\[\[([^\[\]\n]+?)\]\]")


def link_title(text: str | None) -> str:
    """The first line as a link names it: flattened, and a link inside it read as its words, as
    the rendered title shows it -- "[[Alpha]] notes" is named "Alpha notes"."""
    return " ".join(_BRACKETS.sub(r"\1", title_of(text) or "").split())


def link_key(text: str | None) -> str:
    return link_title(text).casefold()


def links_in(text: str) -> list[str]:
    """The keys the text links to, in order, once each."""
    out = [link_key(m.group(2)) for m in LINK.finditer(text or "") if m.group(2)]
    return list(dict.fromkeys(k for k in out if k))


def relink(text: str, old: str, new: str) -> str:
    """`text` with every link naming `old` (a key) renamed to `new` (a title). Code untouched."""

    def swap(m: re.Match) -> str:
        if m.group(2) and link_key(m.group(2)) == old:
            return f"[[{new}]]"
        return m.group(0)

    return LINK.sub(swap, text)


def index_links(conn: sqlite3.Connection, item_id: int, text: str) -> None:
    """Record the item's key and what it links to. Writes only the two link tables."""
    title = link_title(text)
    conn.execute(
        "INSERT INTO item_keys (item_id, key, title) VALUES (?, ?, ?)"
        " ON CONFLICT(item_id) DO UPDATE SET key = excluded.key, title = excluded.title",
        (item_id, title.casefold(), title),
    )
    conn.execute("DELETE FROM item_links WHERE source_id = ?", (item_id,))
    conn.executemany(
        "INSERT INTO item_links (source_id, target) VALUES (?, ?)",
        [(item_id, k) for k in links_in(text) if k],
    )


def reindex_links(conn: sqlite3.Connection) -> int:
    """Rebuild both link tables from the text. Run at startup; they are an index, never a source."""
    rows = conn.execute("SELECT id, raw_text FROM items").fetchall()
    conn.execute("DELETE FROM item_links")
    conn.execute("DELETE FROM item_keys")
    for r in rows:
        index_links(conn, r["id"], r["raw_text"])
    conn.commit()
    return len(rows)


SPACE_LINK = "space:"


def space_of(key: str) -> str | None:
    """The space a key names, for `[[space:coding]]` (phase B), else None. The prefix wins over
    any item whose first line happens to start with it."""
    if not key.startswith(SPACE_LINK):
        return None
    return key[len(SPACE_LINK) :].strip() or None


def rewrite_space_links(conn: sqlite3.Connection, old: str, new: str, allowed) -> None:
    """A space was renamed: `[[space:old]]` becomes `[[space:new]]` in every item that has one,
    through update_fields like an item rename, in the caller's transaction."""
    key = SPACE_LINK + old
    ids = [
        r["source_id"]
        for r in conn.execute("SELECT source_id FROM item_links WHERE target = ?", (key,))
    ]
    for item_id in ids:
        row = conn.execute("SELECT raw_text FROM items WHERE id = ?", (item_id,)).fetchone()
        if row is None:
            continue
        text = relink(row["raw_text"], key, SPACE_LINK + new)
        if text != row["raw_text"]:
            update_fields(conn, item_id, {"text": text}, allowed)


def resolve_link(conn: sqlite3.Connection, key: str) -> int | None:
    if space_of(key) is not None:
        return None  # a space link never opens an item
    row = conn.execute(
        "SELECT i.id FROM item_keys k JOIN items i ON i.id = k.item_id WHERE k.key = ?"
        " ORDER BY i.updated_at DESC, i.id DESC LIMIT 1",
        (key,),
    ).fetchone()
    return row["id"] if row else None


def _rewrite_links_to(
    conn: sqlite3.Connection,
    item_id: int,
    old: str,
    new_key: str,
    new_title: str,
    allowed,
    depth: int,
) -> None:
    """The item's key changed from `old`: rewrite the links that meant it. Not when another item
    still answers to `old` -- those links may mean that one, and it would win them anyway -- and
    not when `[[new_title]]` would not key back to this item (a title only markdown can make, such
    as `**# heading**`); those links dim rather than point somewhere wrong."""
    if not old or not new_title or depth >= MAX_REWRITE_DEPTH:
        return
    if links_in(f"[[{new_title}]]") != [new_key]:
        return
    if conn.execute(
        "SELECT 1 FROM item_keys WHERE key = ? AND item_id != ?", (old, item_id)
    ).fetchone():
        return
    sources = [
        r["source_id"]
        for r in conn.execute(
            "SELECT source_id FROM item_links WHERE target = ? AND source_id != ?",
            (old, item_id),
        ).fetchall()
    ]
    for source_id in sources:
        # Read now, not with the list: a rewrite earlier in this loop can retitle an item that
        # this one links to, and that nested rewrite may already have changed this text.
        row = conn.execute("SELECT raw_text FROM items WHERE id = ?", (source_id,)).fetchone()
        if row is None:
            continue
        text = relink(row["raw_text"], old, new_title)
        if text != row["raw_text"]:
            # Through update_fields, so the linking item's title, key and own backlinks follow,
            # and the touch trigger moves its `updated_at`: an editor open on it gets the
            # changed-elsewhere question instead of saving the old link back over this.
            update_fields(conn, source_id, {"text": text}, allowed, _depth=depth + 1)


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


# --- retrieval (moved here from ask.py in slice 28) ---------------------------------------
# Ask built these; classify needs them too, to find the items a capture might duplicate.
# They live here rather than in ask.py because classify must not import from ask.

MAX_ITEMS = 20

STOPWORDS = frozenset(
    """a about after again all am an and any are as at be because been before being but by
    can could did do does doing down during for from had has have having he her here hers him
    his how i if in into is it its just me more most my no nor not of off on once only or
    other our ours out over own same she should so some such than that the their theirs them
    then there these they this those through to too under until up very was we were what when
    where which while who whom why will with would you your yours decide decided decision
    say said tell told think thought remember note notes wrote write""".split()
)


def _fts_term(word: str) -> str | None:
    """One FTS5 term, or None when the word is not worth searching for. Prefix-matched when
    long enough, so 'decide' finds 'decided'."""
    w = word.lower()
    if w in STOPWORDS or len(w) < 2 or (w.isdigit() and len(w) < 4):
        return None
    return f'"{w}"*' if len(w) >= 4 else f'"{w}"'


def retrieval_query(question: str) -> str:
    """OR of the question's own content words."""
    words = dict.fromkeys(w.lower() for w in re.findall(r"\w+", question, flags=re.UNICODE))
    return " OR ".join(t for w in words if (t := _fts_term(w)))



def _space_clause(space: str | None) -> tuple[str, list[object]]:
    if not space:
        return "", []
    return " AND items.space = ?", [space.strip().lower()]


def search(conn: sqlite3.Connection, match: str, space: str | None) -> list:
    """Items matching an FTS5 query, best first, plus any whose thoughts match it."""
    space_sql, params = _space_clause(space)
    rows = conn.execute(
        "SELECT items.* FROM items_fts JOIN items ON items.id = items_fts.rowid"
        f" WHERE items_fts MATCH ?{space_sql} ORDER BY items_fts.rank, items.id DESC LIMIT ?",
        [match, *params, MAX_ITEMS],
    ).fetchall()
    if len(rows) < MAX_ITEMS:  # and what only an item's thoughts mention
        where = [space_sql.removeprefix(" AND ")] if space_sql else []
        rows += items_by_thoughts(
            conn, match, where, params, [r["id"] for r in rows], MAX_ITEMS - len(rows)
        )
    return rows


CANDIDATES = 8  # similar items shown to the classifier for one capture

# Why an item is waiting. `attention` has had one meaning until now; it has three.
WAIT_NO_SPACE = "no_space"
WAIT_LOW_CONFIDENCE = "low_confidence"
WAIT_DUPLICATE = "duplicate"
WAIT_ASKED = "asked"
# One capture became several items. None of them files itself: the owner decides whether it was
# really several things or one, and "Keep as one" puts it back together (slice 30).
WAIT_SPLIT = "split"
# The note "Keep as one" made. It waits too: the pieces may not have agreed on a space.
WAIT_WHOLE = "whole"


def wait_reason_for(
    space: str | None,
    duplicate_of: int | None,
    parked: bool,
    asked: bool = False,
    split: bool = False,
) -> str | None:
    """The code a waiting row carries. Short, not display text: the client has the matched
    item and writes the sentence itself.

    `asked` comes first among the confident cases, because an item carrying a question is
    waiting on an answer and not on a judgement about confidence. It used to fall through to
    `low_confidence`, so the classifier asking "which space?" at 0.9 rendered as "Unsure (90%)"
    -- which is both wrong and the opposite of what it is doing.

    `split` comes before all of them: it is a question about the whole capture, and keeping it
    as one makes the others moot. A piece's question still shows, from its proposal.
    """
    if split:
        return WAIT_SPLIT
    if parked and duplicate_of is not None:
        return WAIT_DUPLICATE
    if asked:
        return WAIT_ASKED
    if not space:
        return WAIT_NO_SPACE
    return WAIT_LOW_CONFIDENCE


def similar_items(
    conn: sqlite3.Connection, text: str, limit: int = CANDIDATES
) -> tuple[tuple[str, sqlite3.Row], ...]:
    """Filed items that resemble this capture, each paired with the ordinal the model may name.

    The ordinals are `i1`, `i2`, ... and the map back to real ids **never leaves the server**.
    That is the whole defence: an ordinal the model invents resolves to nothing, whereas an id
    it invents can be a real item it was never shown, and a schema check cannot tell the
    difference because a made-up integer is a valid integer.
    """
    match = retrieval_query(text)
    if not match:
        return ()
    rows = [r for r in search(conn, match, None) if r["stage"] == "filed"][:limit]
    return tuple((f"i{n}", row) for n, row in enumerate(rows, start=1))


def resolve_ref(
    candidates: tuple[tuple[str, sqlite3.Row], ...], ref: str | None
) -> int | None:
    """The item id an ordinal points at, or None. Anything unrecognised is None, silently."""
    if not ref:
        return None
    wanted = str(ref).strip().lower()
    for ordinal, row in candidates:
        if ordinal == wanted:
            return int(row["id"])
    return None


CONTEXT_PER_SPACE = 5  # most recent items shown per space in the classifier's context
CONTEXT_EXCERPT = 60  # characters of a note shown there; a task shows its title instead


def item_header(row: sqlite3.Row, ref: str | None = None) -> str:
    """The one line that identifies an item to the AI.

    Both prompts use it: ask puts the item's text and thoughts underneath, classify shows it
    alone as context. One format in one place, so the two prompts cannot drift apart about what
    an item looks like.

    `ref` is the label the model may point at, and it differs on purpose (slice 28). Ask passes
    the real id, because its whole contract is returning `item_ids` and it validates them against
    the set it retrieved. Classify passes an **ordinal** -- an invented ordinal resolves to
    nothing, while an invented id can be a real item the model was never shown, and no schema
    check would catch it. Where the model is not meant to point at anything, `ref` is None and
    no label is printed at all.
    """
    space = row["space"] or "(none)"
    label = f"[{ref}] " if ref else ""
    head = f"{label}{row['created_at'][:10]} · space: {space} · {row['shape']}"
    if row["shape"] == "task":
        head += f": {row['title'] or ''}"
        if row["due"]:
            head += f" · due {row['due']}"
        head += f" · {row['status']}"
    return head


def context_line(row: sqlite3.Row, ref: str | None = None) -> str:
    """One item as the classifier sees it: its shared header, plus the start of a note's text,
    since a note's header has no content in it."""
    line = item_header(row, ref)
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


USAGE_LIMIT = re.compile(r"try again at ([0-9]{1,2}:[0-9]{2}\s*(?:[AP]M)?)", re.I)


def failure_reason(message: str) -> tuple[str, str | None]:
    """(reason, resets_at). The subscription limit is its own kind of failure: it is the scarce
    resource here -- a subscription reports no money cost at all -- and it has stopped work more
    than once. The CLI names the time it will come back; that is worth keeping."""
    text = message or ""
    if "usage limit" in text.lower():
        found = USAGE_LIMIT.search(text)
        return "usage_limit", (found.group(1).strip() if found else None)
    if "timed out" in text.lower():
        return "timeout", None
    return "other", None


QUOTA_KEY = "ai_quota"


def save_quota(conn: sqlite3.Connection, quota) -> None:
    """Remember the most recent rate-limit reading. A point in time, not a history: what matters
    is how full the window is *now*, so this overwrites rather than accumulating. Never raises,
    for the same reason record_call does not."""
    try:
        if not quota:
            return
        primary, secondary = quota
        if not primary.known and not secondary.known:
            return  # the CLI said nothing; keep the last thing it did say
        set_state(
            conn,
            QUOTA_KEY,
            json.dumps(
                {
                    "primary": primary.as_dict(),
                    "secondary": secondary.as_dict(),
                    "at": utcnow_iso(),
                }
            ),
        )
    except (sqlite3.Error, TypeError, ValueError):
        pass


def read_quota(conn: sqlite3.Connection) -> dict | None:
    raw = get_state(conn, QUOTA_KEY)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def record_call(
    conn: sqlite3.Connection,
    *,
    kind: str,
    model: str | None,
    usage=None,
    capture_id: int | None = None,
    duration_ms: int = 0,
    failure: str | None = None,
    shape=None,
) -> None:
    """Write down one AI call. **Never raises**: a bookkeeping failure must not cost a capture."""
    try:
        reason, resets_at = failure_reason(failure) if failure else (None, None)
        counts = {
            f: int(getattr(usage, f, 0) or 0)
            for f in (
                "input_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "output_tokens",
                "reasoning_output_tokens",
                "total_tokens",
            )
        }
        conn.execute(
            "INSERT INTO ai_calls (created_at, kind, model, capture_id, ok, failure, reason,"
            " resets_at, duration_ms, input_tokens, cached_input_tokens,"
            " cache_write_input_tokens, output_tokens, reasoning_output_tokens, total_tokens,"
            " prompt_chars, candidates_n, examples_n, corrections_n, house_rules)"
            " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                utcnow_iso(),
                kind,
                model,
                capture_id,
                0 if failure else 1,
                failure,
                reason,
                resets_at,
                duration_ms,
                *counts.values(),
                int(getattr(shape, "chars", 0) or 0),
                int(getattr(shape, "candidates", 0) or 0),
                int(getattr(shape, "examples", 0) or 0),
                int(getattr(shape, "corrections", 0) or 0),
                1 if getattr(shape, "house_rules", False) else 0,
            ),
        )
        conn.commit()
    except sqlite3.Error:
        pass  # deliberately silent: see the docstring


def usage_totals(conn: sqlite3.Connection) -> dict:
    """What the AI has done, in total. Calls and tokens disagree on purpose: a timed-out call
    is killed before the CLI reports anything, so it costs quota and records no tokens."""
    row = conn.execute(
        "SELECT COUNT(*) AS calls, SUM(ok) AS ok,"
        " COALESCE(SUM(input_tokens), 0) AS input_tokens,"
        " COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,"
        " COALESCE(SUM(cache_write_input_tokens), 0) AS cache_write_input_tokens,"
        " COALESCE(SUM(output_tokens), 0) AS output_tokens,"
        " COALESCE(SUM(reasoning_output_tokens), 0) AS reasoning_output_tokens,"
        " COALESCE(SUM(total_tokens), 0) AS total_tokens,"
        " COALESCE(SUM(duration_ms), 0) AS duration_ms FROM ai_calls"
    ).fetchone()
    # The reset time comes from the most recent row, not MAX() over the column: these are clock
    # strings like "11:46 AM", so a lexicographic max puts "9:30 PM" above "11:46 AM" and the UI
    # -- which says "last reporting a reset at ..." -- showed a time from some older row.
    limits = conn.execute(
        "SELECT COUNT(*) AS n, MAX(created_at) AS last,"
        " (SELECT resets_at FROM ai_calls WHERE reason = 'usage_limit'"
        "  ORDER BY created_at DESC, id DESC LIMIT 1) AS resets"
        " FROM ai_calls WHERE reason = 'usage_limit'"
    ).fetchone()
    captures = conn.execute(
        "SELECT COUNT(DISTINCT capture_id) AS n FROM ai_calls WHERE capture_id IS NOT NULL"
    ).fetchone()["n"]
    out = {k: int(row[k] or 0) for k in row.keys() if k != "ok"}
    out["failed"] = int(row["calls"] or 0) - int(row["ok"] or 0)
    out["captures"] = int(captures or 0)
    shape = conn.execute(
        "SELECT AVG(prompt_chars) AS prompt_chars, MAX(prompt_chars) AS prompt_chars_max,"
        " SUM(candidates_n) AS candidates, SUM(examples_n) AS examples,"
        " SUM(corrections_n) AS corrections_used, SUM(house_rules) AS with_house_rules"
        " FROM ai_calls WHERE kind = 'classify' AND prompt_chars > 0"
    ).fetchone()
    out["prompt"] = {k: int(shape[k] or 0) for k in shape.keys()}
    out["usage_limit"] = {
        "count": int(limits["n"] or 0),
        "last": limits["last"],
        "resets_at": limits["resets"],
    }
    return out


def usage_for_capture(conn: sqlite3.Connection, capture_id: int) -> dict | None:
    """What one capture's classification consumed, or None when nothing was recorded -- every
    item filed before slice 29 has no row and never will."""
    row = conn.execute(
        "SELECT COALESCE(SUM(input_tokens), 0) AS input_tokens,"
        " COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,"
        " COALESCE(SUM(cache_write_input_tokens), 0) AS cache_write_input_tokens,"
        " COALESCE(SUM(output_tokens), 0) AS output_tokens,"
        " COALESCE(SUM(total_tokens), 0) AS total_tokens,"
        " COALESCE(SUM(duration_ms), 0) AS duration_ms, COUNT(*) AS calls"
        " FROM ai_calls WHERE capture_id = ?",
        (capture_id,),
    ).fetchone()
    if not row or not int(row["calls"] or 0):
        return None
    return {k: int(row[k] or 0) for k in row.keys()}


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
    duplicate_of: int | None = None,
    wait_reason: str | None = None,
) -> int:
    values = _clean(fields, allowed)
    if stage == "filed" and not values.get("space"):
        raise SpaceError("a space is required to file an item")
    if values.get("shape") == "task":
        raw_text = retitle(raw_text, values.get("title"))
        values["title"] = title_of(raw_text)
    cols = [
        "capture_id",
        "raw_text",
        "created_at",
        "stage",
        "proposal_json",
        "proposal_error",
        "classified_at",
        "updated_at",
        "duplicate_of",
        "wait_reason",
        *values.keys(),
    ]
    # One timestamp for both, so "never touched since it was written" is `updated_at =
    # classified_at`: any later edit moves `updated_at` through the touch trigger. Keep as one
    # depends on it. Milliseconds, as the trigger writes them: `updated_at` is compared as a
    # string, and "…:00Z" sorts after "…:00.100Z" from the same second.
    now = utcnow_ms_iso()
    params = [
        capture_id,
        raw_text,
        created_at,
        stage,
        proposal_json,
        proposal_error,
        now,
        now,
        duplicate_of,
        wait_reason,
        *values.values(),
    ]
    cur = conn.execute(
        f"INSERT INTO items ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})", params
    )
    item_id = int(cur.lastrowid or 0)
    index_links(conn, item_id, raw_text)
    return item_id


class NotWhole(Exception):
    """Keep as one refused: the capture did not split, or someone has started on a piece."""


def _untouched_split(conn: sqlite3.Connection, capture_id: int) -> list[sqlite3.Row] | None:
    """The capture's pieces, if Keep as one may still replace them; else None.

    Every item the capture has must still be a waiting `split` piece nobody has started on: not
    approved, edited, answered, redone, thought about or worked on in a session -- the same
    spirit as the retry rule. A deleted piece does not count against it: Keep as one brings
    back the whole text anyway."""
    rows = conn.execute(
        "SELECT *, EXISTS (SELECT 1 FROM sessions s WHERE s.item_id = items.id) AS worked"
        " FROM items WHERE capture_id = ? ORDER BY id",
        (capture_id,),
    ).fetchall()
    ok = bool(rows) and all(
        r["stage"] == "attention"
        and r["wait_reason"] == WAIT_SPLIT
        and r["updated_at"] == r["classified_at"]
        and r["thought_count"] == 0
        and r["feedback"] is None
        and not r["worked"]
        for r in rows
    )
    return rows if ok else None


def split_info(conn: sqlite3.Connection, items: Sequence[dict]) -> None:
    """Add `split: {of, whole}` to each waiting split piece: how many pieces its capture has,
    and whether Keep as one is still on offer."""
    seen: dict[int, dict] = {}
    for item in items:
        if item.get("wait_reason") != WAIT_SPLIT:
            continue
        cid = item["capture_id"]
        if cid not in seen:
            rows = conn.execute(
                "SELECT COUNT(*) FROM items WHERE capture_id = ?", (cid,)
            ).fetchone()[0]
            seen[cid] = {"of": rows, "whole": _untouched_split(conn, cid) is not None}
        item["split"] = seen[cid]


MAX_OPTIONS = 6  # the most answers a question may offer, as for the classifier's own


def keep_whole(conn: sqlite3.Connection, capture_id: int) -> int:
    """Replace a split capture's pieces with one waiting note holding the capture's whole text.

    Its space is the one every piece proposed; if they disagreed, it asks which, with their
    spaces as the answers. Always a note: tasks cannot be merged, and one tap makes it a task.
    Raises NotWhole when the pieces are not all untouched."""
    cap = conn.execute(
        "SELECT raw_text, created_at FROM captures WHERE id = ?", (capture_id,)
    ).fetchone()
    if cap is None:
        raise NotWhole("no such capture")
    rows = _untouched_split(conn, capture_id)
    if rows is None:
        raise NotWhole("Only while every piece is still waiting and untouched.")
    allowed = list_spaces(conn)
    spaces = list(dict.fromkeys(r["space"] for r in rows if r["space"] in allowed))
    confidences = [
        json.loads(r["proposal_json"]).get("confidence", 0) for r in rows if r["proposal_json"]
    ]
    proposal: dict = {
        "shape": "note",
        "space": spaces[0] if len(spaces) == 1 else None,
        "title": None,
        "due": None,
        "remind_at": None,
        "confidence": min(confidences, default=0),
        "clarify": None,
        "duplicate_of": None,
        "new_space": None,
    }
    if len(spaces) > 1:
        proposal["clarify"] = {
            "field": "space",
            "question": "Where does this go?",
            "options": [
                {"value": s, "label": s, "detail": None} for s in spaces[:MAX_OPTIONS]
            ],
        }
    item_id = insert_item(
        conn,
        capture_id=capture_id,
        raw_text=cap["raw_text"],
        created_at=cap["created_at"],
        fields={"shape": "note", "space": proposal["space"]},
        stage="attention",
        allowed=allowed,
        proposal_json=json.dumps(proposal),
        wait_reason=WAIT_WHOLE,
    )
    marks = ", ".join("?" * len(rows))
    conn.execute(f"DELETE FROM items WHERE id IN ({marks})", [r["id"] for r in rows])
    return item_id


def update_fields(
    conn: sqlite3.Connection,
    item_id: int,
    fields: dict,
    allowed: Sequence[str],
    *,
    _depth: int = 0,
) -> None:
    """Apply editable fields. Raises SpaceError for a bad space; the DB rejects filed + null.

    A text change re-indexes the item's links, and a changed first line rewrites the links to
    it in other items, in the caller's transaction (slice 33)."""
    values = _clean(fields, allowed)
    if not values:
        return
    if {"raw_text", "title", "shape"} & values.keys():
        row = conn.execute(
            "SELECT raw_text, shape FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        if row is not None and values.get("shape", row["shape"]) == "task":
            # A title edit -- the approval card's quoted word -- is an edit of line one.
            text = values.get("raw_text", row["raw_text"])
            if "title" in values and "raw_text" not in values:
                # Line one is the title, so renaming it is rewriting that line. Moving a note to a
                # task is the same call with the note's first line already there.
                text = retitle(text, values["title"], replace=row["shape"] == "task")
                if text != row["raw_text"]:
                    values["raw_text"] = text
            values["title"] = title_of(text)
    if "starred" in values:
        # Any star set or cleared by a person is theirs from then on: Pick for me removes only the
        # stars it set itself (slice 32), so touching one hands it over.
        values["picked_at"] = None
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
    old_key = None
    if "raw_text" in values:
        row = conn.execute("SELECT key FROM item_keys WHERE item_id = ?", (item_id,)).fetchone()
        old_key = row["key"] if row else None
    assignments = ", ".join(f"{k} = ?" for k in values)
    conn.execute(f"UPDATE items SET {assignments} WHERE id = ?", (*values.values(), item_id))
    if "raw_text" in values:
        index_links(conn, item_id, values["raw_text"])
        new_key = link_key(values["raw_text"])
        if old_key and new_key != old_key:
            new_title = link_title(values["raw_text"])
            _rewrite_links_to(conn, item_id, old_key, new_key, new_title, allowed, _depth)


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
    # `fields`, not `values`: `update_fields` cleans what it is given, and cleaning twice loses
    # a `text` edit -- the first pass renames it to `raw_text`, which is not an editable field
    # name, so the second pass drops it. `approve` accepted the edit and answered 200 while
    # discarding the write, where PATCH on the same body kept it.
    update_fields(conn, item_id, fields, allowed)
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
