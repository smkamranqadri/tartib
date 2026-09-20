"""Classifier eval against the real Codex CLI. Run with `uv run pytest -m eval` (about 30s;
the captures run concurrently).

22 captures: 4 multi-item, 2 questions, 2 with no clear space, 2 verb-less tasks, 1 timed
reminder, 5 plain, and 6 dateless: 4 concrete tasks that should be given a near-term date and 2
open-ended ones that should stay undated. Asserts shape, split count, space where unambiguous,
due dates where expected, and that no proposal carries a space outside TARTIB_SPACES. Failures
are collected and reported together.
"""

from __future__ import annotations

import asyncio
import shutil
from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from tartib.classify import Context, classify
from tartib.codex import CodexConfig
from tartib.store import SpaceContext

SPACES = ["work", "home", "health", "finance", "ideas", "travel"]
ZONE = ZoneInfo("Asia/Karachi")
NOW = datetime(2026, 9, 17, 10, 0, tzinfo=ZONE)  # a Thursday

ANY = object()

# (text, expected shapes in order, expected spaces per proposal (str | set | None | ANY), flags)
FIXTURES = [
    # multi-item
    (
        "Renew passport before the trip, call the dentist tomorrow, and buy milk",
        ["task", "task", "task"],
        ["travel", "health", "home"],
        {},
    ),
    (
        "- pay the electricity bill\n- book the car service\n- send the invoice to Ahmed",
        ["task", "task", "task"],
        [{"home", "finance"}, {"home", None}, {"work", "finance"}],
        {},
    ),
    (
        "Ali said the API rate limit is 100 requests per minute."
        " Decided we cache responses for 30s.",
        ["note", "note"],
        ["work", "work"],
        {},
    ),
    (
        "fix the login bug in tartib, and pray fajr on time tomorrow",
        ["task", "task"],
        [ANY, ANY],
        {"due_last": "2026-09-18"},
    ),
    # questions
    ("what did Ali say about the API rate limits?", ["question"], [None], {}),
    ("when did I last go to the dentist?", ["question"], [None], {}),
    # no clear space: must end up needing a human (null space, or confidence below the gate)
    (
        "Lorem ipsum dolor sit amet, nothing to do with anything",
        ["note"],
        [ANY],
        {"attention": True},
    ),
    ("xq7 zz plorb", ["note"], [ANY], {"attention": True}),
    # verb-less tasks
    ("Ping Sara re: Thursday", ["task"], [ANY], {}),
    ("Dentist 3pm Friday", ["task"], ["health"], {"due": "2026-09-18"}),
    # timed reminder
    (
        "remind me at 6pm to water the plants",
        ["task"],
        ["home"],
        {"remind_at": "2026-09-17T13:00:00+00:00"},
    ),
    # plain
    ("Decided to learn Rust next, not Go", ["note"], [{"ideas", "work"}], {}),
    ("Book flights to Lahore for the 3rd of October", ["task"], ["travel"], {"due": "2026-10-03"}),
    ("The office wifi password is written on the whiteboard", ["note"], ["work"], {}),
    ("Move the emergency fund to the Meezan savings account", ["task"], ["finance"], {}),
    ("Standup moved to 10:30", ["note"], ["work"], {}),
    # dateless tasks: concrete ones get a near-term date, open-ended ones stay undated
    ("follow up with the dentist about the crown", ["task"], ["health"], {"due_in": (1, 2)}),
    ("pick up the dry cleaning", ["task"], ["home"], {"due_in": (1, 2)}),
    (
        "reply to Ahmed's email about the invoice",
        ["task"],
        [{"work", "finance"}],
        {"due_in": (1, 2)},
    ),
    ("organise the bookshelf", ["task"], ["home"], {"due_in": (1, 7)}),
    ("learn to play the oud one day", [{"task", "note"}], [ANY], {"undated": True}),
    ("drink more water", [{"task", "note"}], [{"health", None}], {"undated": True}),
]


def _shape_ok(expected, got) -> bool:
    return got in expected if isinstance(expected, set) else got == expected


def _space_ok(expected, got) -> bool:
    if expected is ANY:
        return True
    if isinstance(expected, set):
        return got in expected
    return got == expected


@pytest.mark.eval
def test_classifier_eval():
    if shutil.which("codex") is None:
        pytest.skip("codex CLI not installed")
    context = Context(now=NOW, zone=ZONE, spaces=SPACES, codex=CodexConfig(command="codex"))

    async def run_all():
        return await asyncio.gather(*(classify(text, context) for text, *_ in FIXTURES))

    results = asyncio.run(run_all())
    failures: list[str] = []
    for (text, shapes, spaces, flags), proposals in zip(FIXTURES, results, strict=True):
        got_shapes = [p.shape for p in proposals]
        got_spaces = [p.space for p in proposals]
        tag = f"{text[:50]!r}: got {list(zip(got_shapes, got_spaces, strict=True))}"
        if len(proposals) != len(shapes):
            failures.append(f"{tag} -> expected {len(shapes)} proposals")
            continue
        if not all(_shape_ok(e, g) for e, g in zip(shapes, got_shapes, strict=True)):
            failures.append(f"{tag} -> expected shapes {shapes}")
        for exp, got in zip(spaces, got_spaces, strict=True):
            if not _space_ok(exp, got):
                failures.append(f"{tag} -> expected space {exp}")
        for p in proposals:
            if p.space is not None and p.space not in SPACES:
                failures.append(f"{tag} -> space {p.space!r} outside TARTIB_SPACES")
            if p.shape == "question" and (p.space or p.title or p.due or p.remind_at):
                failures.append(f"{tag} -> question carries fields")
        p0 = proposals[0]
        if flags.get("attention") and not (p0.space is None or p0.confidence < 0.85):
            failures.append(
                f"{tag} -> should need a human (space {p0.space}, conf {p0.confidence})"
            )
        if "due" in flags and (p0.due.isoformat() if p0.due else None) != flags["due"]:
            failures.append(f"{tag} -> due {p0.due} expected {flags['due']}")
        if "due_in" in flags:
            lo, hi = flags["due_in"]
            days = (p0.due - NOW.date()).days if p0.due else None
            if days is None or not lo <= days <= hi:
                failures.append(f"{tag} -> due {p0.due} expected {lo} to {hi} days out")
        if flags.get("undated") and any(p.due for p in proposals):
            failures.append(f"{tag} -> due {[p.due for p in proposals]} expected none")
        last = proposals[-1]
        if (
            "due_last" in flags
            and (last.due.isoformat() if last.due else None) != flags["due_last"]
        ):
            failures.append(f"{tag} -> last due {last.due} expected {flags['due_last']}")
        if (
            "remind_at" in flags
            and (p0.remind_at.isoformat() if p0.remind_at else None) != flags["remind_at"]
        ):
            failures.append(f"{tag} -> remind_at {p0.remind_at} expected {flags['remind_at']}")
    if failures:
        pytest.fail("\n".join(failures))


# Tell it why: (text, earlier proposal, the person's reason, expected shape, expected space).
# The third keeps the space: a reason about the shape must not move the item elsewhere.
REDO_FIXTURES = [
    (
        "call Sara about the lease",
        {"shape": "note", "space": "work", "title": None, "due": None, "confidence": 0.5},
        "it is something I have to do, and it is about my flat, so home",
        "task",
        "home",
    ),
    (
        "Book the car service",
        {"shape": "task", "space": "finance", "title": "Book the car service", "confidence": 0.6},
        "not money, this is a house thing",
        "task",
        "home",
    ),
    (
        "Standup moved to 10:30",
        {"shape": "task", "space": "work", "title": "Move standup", "confidence": 0.6},
        "that is just information, nothing to do",
        "note",
        "work",
    ),
]


@pytest.mark.eval
def test_a_reason_moves_the_answer():
    if shutil.which("codex") is None:
        pytest.skip("codex CLI not installed")
    import json

    context = Context(now=NOW, zone=ZONE, spaces=SPACES, codex=CodexConfig(command="codex"))

    async def run_all():
        return await asyncio.gather(
            *(
                classify(text, context, correction=(json.dumps(earlier), reason))
                for text, earlier, reason, *_ in REDO_FIXTURES
            )
        )

    failures = []
    for (text, _, reason, shape, space), proposals in zip(
        REDO_FIXTURES, asyncio.run(run_all()), strict=True
    ):
        p = next((p for p in proposals if p.shape != "question"), None)
        got = (p.shape, p.space) if p else None
        if got != (shape, space):
            failures.append(f"{text!r} + {reason!r}: got {got}, expected {(shape, space)}")
    if failures:
        pytest.fail("\n".join(failures))


# --- slice 26: does showing the classifier what already exists make it file better? ---
#
# These captures are deliberately unanswerable from the space names alone. Each turns on a
# proper noun -- a contractor, a transit card, a co-writer -- that means nothing until you have
# seen where similar items already live. A flat list of six space names cannot place any of
# them; the point of the measurement is whether the context can.

CONTEXT_ITEMS = {
    "work": [
        ("task", "Send Ahmed the Q3 deck", None),
        ("note", None, "Tartib deploy runs on CapRover, image tagged per version."),
        ("task", "Move standup to 10:30", None),
    ],
    "home": [
        ("note", None, "Meridian quoted 40k for the roof, valid until the 30th."),
        ("task", "Ask Bilal to look at the kitchen leak", None),
        ("note", None, "Spare keys are with the neighbour on the left."),
    ],
    "health": [
        ("note", None, "Physio: swim twice a week, lane 3 before 7am."),
        ("note", None, "The blue goggles are the ones that do not leak."),
        ("task", "Book the next physio session", None),
    ],
    "finance": [
        ("note", None, "Astra motor policy renews yearly, premium 48k."),
        ("task", "Pay the electricity bill", None),
        ("note", None, "Invoices go out on the first of the month."),
    ],
    "ideas": [
        ("note", None, "Sahar is co-writing the piece on attention and tools."),
        ("note", None, "A graph of items, sized by how often each is referenced."),
        ("note", None, "Write something about why queues beat retries."),
    ],
    "travel": [
        ("note", None, "Kalmar card is the transit card for the Stockholm trip."),
        ("task", "Renew passport before the trip", None),
        ("note", None, "Flights are cheapest on Tuesday mornings."),
    ],
}

# (capture, the space only the context can point to)
DISCRIMINATING = [
    ("Chase up the Meridian quote", "home"),
    ("Top up the Kalmar card", "travel"),
    ("Ping Sahar about the draft", "ideas"),
    ("Order more of the blue ones", "health"),
    ("Renew Astra before the 30th", "finance"),
    ("Ask Bilal to come back and look at it again", "home"),
]


def _fake_context() -> tuple[SpaceContext, ...]:
    """The same shape store.classify_context builds, without needing a database."""
    out = []
    for i, name in enumerate(SPACES):
        lines = []
        for j, (shape, title, text) in enumerate(CONTEXT_ITEMS[name]):
            head = f"[id {i * 10 + j}] 2026-09-1{j} · space: {name} · {shape}"
            lines.append(f"{head}: {title} · open" if shape == "task" else f"{head}: {text}")
        tasks = sum(1 for s, _, _ in CONTEXT_ITEMS[name] if s == "task")
        out.append(
            SpaceContext(
                name=name,
                open_tasks=tasks,
                notes=len(CONTEXT_ITEMS[name]) - tasks,
                recent=tuple(lines),
            )
        )
    return tuple(out)


def _score(existing: tuple[SpaceContext, ...]) -> tuple[int, list[str]]:
    context = Context(
        now=NOW, zone=ZONE, spaces=SPACES, codex=CodexConfig(command="codex"), existing=existing
    )

    async def run_all():
        return await asyncio.gather(*(classify(text, context) for text, _ in DISCRIMINATING))

    got = 0
    detail = []
    for (text, want), proposals in zip(DISCRIMINATING, asyncio.run(run_all()), strict=True):
        p = next((p for p in proposals if p.shape != "question"), None)
        space = p.space if p else None
        if space == want:
            got += 1
        detail.append(f"{text[:34]!r} -> {space} (want {want})")
    return got, detail


@pytest.mark.eval
def test_context_beats_a_flat_list_of_space_names():
    """The measurement slice 26 exists for. Both numbers are reported either way."""
    if shutil.which("codex") is None:
        pytest.skip("codex CLI not installed")

    blind, blind_detail = _score(())
    seeing, seeing_detail = _score(_fake_context())
    total = len(DISCRIMINATING)
    report = (
        f"\nspace names only: {blind}/{total}\n  " + "\n  ".join(blind_detail) +
        f"\nwith what already exists: {seeing}/{total}\n  " + "\n  ".join(seeing_detail)
    )
    print(report)
    assert seeing >= blind, f"the context made filing worse{report}"
