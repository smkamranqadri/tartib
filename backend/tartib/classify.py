"""classify(text, context) -> list[Proposal]. Runs through the shared Codex transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tartib.codex import CodexConfig, CodexError, run_json
from tartib.store import SpaceContext

NULL_SPACE_CONFIDENCE_CAP = 0.6
CONTEXT_BUDGET = 4000  # characters; this block rides on every capture


class ClassifyError(Exception):
    """Classification failed; the message is stored on the fallback item as proposal_error."""


class Proposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shape: Literal["task", "note", "question"]
    text: str | None = None
    space: str | None = None
    title: str | None = None
    due: date | None = None
    remind_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)

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
    "required": ["shape", "text", "space", "title", "due", "remind_at", "confidence"],
    "properties": {
        "shape": {"type": "string", "enum": ["task", "note", "question"]},
        "text": {"type": ["string", "null"]},
        "space": {"type": ["string", "null"]},
        "title": {"type": ["string", "null"]},
        "due": {"type": ["string", "null"]},
        "remind_at": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
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

Never rewrite or summarize the text itself. Do not run commands or read files.

Current datetime: {now} ({zone})
Existing spaces: {spaces}
{existing}
Text:
{text}"""


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
        text=text,
    )
    if correction is not None:
        earlier, reason = correction
        head, _, tail = prompt.rpartition("\n\nText:\n")
        prompt = head + CORRECTION.format(earlier=earlier, reason=reason) + "\n\nText:\n" + tail
    return prompt


def _normalize(p: Proposal, context: Context) -> Proposal:
    """Enforce the rules the prompt states, whatever the model did.

    Questions carry nothing. Notes carry no task fields. Unknown spaces become null and cap
    confidence. Naive reminder times are in the user's zone; store UTC."""
    update: dict = {}
    if p.shape == "question":
        update.update(space=None, title=None, due=None, remind_at=None)
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
