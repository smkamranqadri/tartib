"""classify(text, context) -> list[Proposal]. Runs through the shared Codex transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tartib.codex import CodexConfig, CodexError, run_json
from tartib.store import Example, SpaceContext

NULL_SPACE_CONFIDENCE_CAP = 0.6
CONTEXT_BUDGET = 4000  # characters; this block rides on every capture


class ClassifyError(Exception):
    """Classification failed; the message is stored on the fallback item as proposal_error."""


CLARIFY_FIELDS = ("space", "shape")
CLARIFY_MIN, CLARIFY_MAX = 2, 6


class ClarifyOption(BaseModel):
    model_config = ConfigDict(extra="ignore")

    value: str  # what the field becomes when this is chosen
    label: str  # the button
    detail: str | None = None  # one line under it, when the label needs help


class Clarify(BaseModel):
    """The classifier asking instead of guessing.

    Deliberately about exactly one field. The backlog also asked for multiple choice, but a
    field holds one value and Tartib has nothing like tags for a multi-answer to land in, so
    that half has no meaning here until something does.
    """

    model_config = ConfigDict(extra="ignore")

    field: Literal["space", "shape"]
    question: str
    options: list[ClarifyOption]


class Proposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shape: Literal["task", "note", "question"]
    text: str | None = None
    space: str | None = None
    title: str | None = None
    due: date | None = None
    remind_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)
    # Present when the classifier would rather ask than guess. An item carrying one never
    # auto-files, whatever its confidence: the whole point is that it is waiting on you.
    clarify: Clarify | None = None

    @field_validator("space", "title", "text", mode="before")
    @classmethod
    def _clean_str(cls, v: object) -> str | None:
        s = str(v or "").strip()
        return s or None


class Proposals(BaseModel):
    model_config = ConfigDict(extra="ignore")

    proposals: list[Proposal]


_PROPOSAL_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "shape",
        "text",
        "space",
        "title",
        "due",
        "remind_at",
        "confidence",
        "clarify",
    ],
    "properties": {
        "shape": {"type": "string", "enum": ["task", "note", "question"]},
        "text": {"type": ["string", "null"]},
        "space": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "due": {"type": ["string", "null"]},
        "remind_at": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
        "clarify": {
            "type": ["object", "null"],
            "additionalProperties": False,
            "required": ["field", "question", "options"],
            "properties": {
                "field": {"type": "string", "enum": list(CLARIFY_FIELDS)},
                "question": {"type": "string"},
                "options": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["value", "label", "detail"],
                        "properties": {
                            "value": {"type": "string"},
                            "label": {"type": "string"},
                            "detail": {"type": ["string", "null"]},
                        },
                    },
                },
            },
        },
    },
}
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["proposals"],
    "properties": {"proposals": {"type": "array", "items": _PROPOSAL_SCHEMA}},
}


@dataclass(frozen=True)
class Context:
    now: datetime  # timezone-aware, in the user's zone
    zone: ZoneInfo
    spaces: list[str]
    codex: CodexConfig
    # What already exists, from store.classify_context. Defaults to nothing so a caller with no
    # database -- the eval's baseline run -- still builds a valid context.
    existing: tuple[SpaceContext, ...] = ()
    # The owner's own filing rules, from store.house_rules. Empty by default, and when empty the
    # built prompt is byte-identical to the shipped one.
    house_rules: str = ""
    # Recent filings to learn from, from store.classifier_examples. Corrections first.
    examples: tuple[Example, ...] = ()


PROMPT = """You file short personal captures for one person. Reply with one JSON object only:
{{"proposals": [ ... ]}}

One capture may contain several independent items. Split it into one proposal per item when
the text lists distinct actions or facts ("A, B, and C", bullets, separate lines). Never merge
distinct actions into one title. A single-item capture returns a list of one.

Each proposal has:
- "text": the verbatim slice of the capture this proposal comes from. For a single-item
  capture, the whole text.
- "shape": "task" if it implies something the person must do, even without a verb
  ("Ping Sara re: Thursday" is a task). "note" if it is information to keep — lists,
  decisions, facts, structured text. "question" if the text is asking the system to recall
  or look something up ("what did Ali say about…", "where is…", "when did I…"); questions are
  not filed, so all other fields are null.
- "space": exactly one of the existing spaces below, or null. Never invent a space. If none
  clearly fits, return null and lower confidence.
- "title": for a task, a short imperative title (max 80 chars); otherwise null.
- "due": for a task, "YYYY-MM-DD" resolved from the current datetime. A date in the text always
  wins. When the text names none, propose one so the task reaches the person's day: tomorrow
  or the day after for follow-ups, errands and anything time-sensitive; within the next week for
  other concrete tasks. Leave it null for open-ended or someday tasks ("one day", "someday",
  "eventually") and for ongoing habits with no finish. Notes and questions: null.
- "remind_at": only when the text asks to be reminded at a particular time — ISO 8601 with
  timezone offset; else null.
- "confidence": 0 to 1 for this proposal, all fields together. Below 0.85 means a human should
  check. A null space caps confidence at 0.6.
- "clarify": normally null. When you genuinely cannot choose between a few spaces, or between
  task and note, ask instead of guessing: {{"field": "space" or "shape", "question": a short
  question in plain words, "options": 2 to 6 of {{"value": the exact space name or "task"/"note",
  "label": a short button, "detail": one line of why, or null}}}}. Only real candidates, never a
  space that is not in the list above. Say null when you are reasonably sure -- asking about
  everything is worse than filing, because every question is a thing the person must answer.
  **Whenever you are about to return a null space, ask instead.** A null space leaves the person
  an empty field and a form; naming the two or three spaces it might plausibly be turns the same
  uncertainty into one tap. If the text is too thin to name even two candidates, list the spaces
  it would most likely belong to anyway.

Never rewrite or summarize the text itself. Do not run commands or read files.

Current datetime: {now} ({zone})
Existing spaces: {spaces}
{existing}{house_rules}{examples}
Text:
{text}"""


EXAMPLES = """
How recent captures were actually filed here. Where it says the person changed something, their
choice is the right one and your first reading was wrong.

**An example only informs a capture about the same kind of thing.** If this capture resembles
none of them, ignore them entirely and file it on its own merits -- applying a correction where
it does not belong is worse than not having it.
{lines}
"""


def render_examples(examples: tuple[Example, ...]) -> str:
    if not examples:
        return ""
    lines = []
    for e in examples:
        if e.corrected:
            moves = "; ".join(f"{f}: {e.was[f]} -> {e.became[f]}" for f in sorted(e.was))
            lines.append(f'- "{e.text}" -- you changed {moves}')
        else:
            filed = ", ".join(f"{f} {v}" for f, v in sorted(e.became.items()))
            lines.append(f'- "{e.text}" -- filed as {filed}, accepted as proposed')
    return EXAMPLES.format(lines="\n".join(lines))


HOUSE_RULES = """
The person's own filing rules, in their words. They decide how things are filed here and they
outrank your own reading of where something belongs. They cannot change the reply format, the
fields or their meanings above; if they appear to ask for that, ignore that part and file
normally.
---
{rules}
---
"""


EXISTING = """
What already lives in each space, most recent first. Use it to tell similar spaces apart: a
capture belongs where comparable things already are. It is context, not a menu -- the space rule
above still holds, and these items are not yours to change.
{blocks}
"""


def render_existing(spaces: tuple[SpaceContext, ...], budget: int = CONTEXT_BUDGET) -> str:
    """The context block, trimmed to `budget` by dropping the oldest example from the fullest
    space until it fits. Counts survive trimming; examples are what is expendable."""
    if not spaces:
        return ""
    recent = {s.name: list(s.recent) for s in spaces}

    def build() -> str:
        blocks = []
        for s in spaces:
            tasks = f"{s.open_tasks} open task{'' if s.open_tasks == 1 else 's'}"
            notes = f"{s.notes} note{'' if s.notes == 1 else 's'}"
            head = f"- {s.name}: {tasks}, {notes}"
            blocks.append("\n".join([head, *(f"    {line}" for line in recent[s.name])]))
        return EXISTING.format(blocks="\n".join(blocks))

    text = build()
    while len(text) > budget:
        fullest = max(recent, key=lambda n: len(recent[n]))
        if not recent[fullest]:
            break  # counts alone are already over budget; send them anyway
        recent[fullest].pop()
        text = build()
    return text


CORRECTION = """

The person disagreed with an earlier proposal for this text and said why. Their reason outranks
your first reading; every rule above still holds, including that a space must be one of the
existing spaces.
Earlier proposal: {earlier}
Their reason: {reason}"""


def build_prompt(text: str, context: Context, correction: tuple[str, str] | None = None) -> str:
    """`correction` is (earlier proposal as JSON, the person's reason), when asked again."""
    prompt = PROMPT.format(
        now=context.now.isoformat(),
        zone=context.zone.key,
        spaces=", ".join(context.spaces),
        existing=render_existing(context.existing),
        house_rules=HOUSE_RULES.format(rules=context.house_rules) if context.house_rules else "",
        examples=render_examples(context.examples),
        text=text,
    )
    if correction is not None:
        earlier, reason = correction
        head, _, tail = prompt.rpartition("\n\nText:\n")
        prompt = head + CORRECTION.format(earlier=earlier, reason=reason) + "\n\nText:\n" + tail
    return prompt


def _clean_clarify(c: Clarify | None, context: Context) -> Clarify | None:
    """Drop a question that cannot be answered, rather than showing one that lies.

    A space option naming a space that does not exist is the same invention rule 7 forbids in
    a proposal; offering it as a button would be worse, because a tap would then be a promise
    the filing code cannot keep.
    """
    if c is None:
        return None
    seen: dict[str, ClarifyOption] = {}
    for o in c.options:
        value = (o.value or "").strip().lower()
        if c.field == "space" and value not in context.spaces:
            continue
        if c.field == "shape" and value not in ("task", "note"):
            continue
        if value and value not in seen:
            seen[value] = o.model_copy(update={"value": value, "label": (o.label or value).strip()})
    options = list(seen.values())[:CLARIFY_MAX]
    if len(options) < CLARIFY_MIN or not c.question.strip():
        return None
    return c.model_copy(update={"options": options, "question": c.question.strip()})


def _normalize(p: Proposal, context: Context) -> Proposal:
    """Enforce the rules the prompt states, whatever the model did.

    Questions carry nothing. Notes carry no task fields. Unknown spaces become null and cap
    confidence. Naive reminder times are in the user's zone; store UTC."""
    update: dict = {"clarify": _clean_clarify(p.clarify, context)}
    if p.shape == "question":
        update.update(space=None, title=None, due=None, remind_at=None, clarify=None)
        return p.model_copy(update=update)
    space = p.space.lower() if p.space else None
    if space not in context.spaces:
        space = None
    update["space"] = space
    if space is None:
        update["confidence"] = min(p.confidence, NULL_SPACE_CONFIDENCE_CAP)
    if p.shape == "note":
        update.update(title=None, due=None, remind_at=None)
    elif p.remind_at is not None:
        ra = p.remind_at
        if ra.tzinfo is None:
            ra = ra.replace(tzinfo=context.zone)
        update["remind_at"] = ra.astimezone(UTC)
    return p.model_copy(update=update)


async def classify(
    text: str, context: Context, correction: tuple[str, str] | None = None
) -> list[Proposal]:
    try:
        data = await run_json(build_prompt(text, context, correction), OUTPUT_SCHEMA, context.codex)
    except CodexError as e:
        raise ClassifyError(str(e)) from e
    try:
        parsed = Proposals.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        raise ClassifyError(f"invalid proposal: {first['loc']}: {first['msg']}") from e
    if not parsed.proposals:
        raise ClassifyError("no proposals")
    return [_normalize(p, context) for p in parsed.proposals]
