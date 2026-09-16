"""classify(text, context) -> Proposal. Runs through the shared Codex transport."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from tartib.codex import CodexConfig, CodexError, run_json


class ClassifyError(Exception):
    """Classification failed; the message is stored on the item as proposal_error."""


class Proposal(BaseModel):
    model_config = ConfigDict(extra="ignore")

    shape: Literal["task", "note"]
    space: str = "inbox"
    title: str | None = None
    due: date | None = None
    remind_at: datetime | None = None
    confidence: float = Field(ge=0, le=1)

    @field_validator("space", mode="before")
    @classmethod
    def _clean_space(cls, v: object) -> str:
        s = str(v or "").strip().lower()
        return s or "inbox"

    @field_validator("title", mode="before")
    @classmethod
    def _clean_title(cls, v: object) -> str | None:
        s = str(v or "").strip()
        return s or None


# Strict so the model cannot add fields.
OUTPUT_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["shape", "space", "title", "due", "remind_at", "confidence"],
    "properties": {
        "shape": {"type": "string", "enum": ["task", "note"]},
        "space": {"type": "string"},
        "title": {"type": ["string", "null"]},
        "due": {"type": ["string", "null"]},
        "remind_at": {"type": ["string", "null"]},
        "confidence": {"type": "number"},
    },
}


@dataclass(frozen=True)
class Context:
    now: datetime  # timezone-aware, in the user's zone
    zone: ZoneInfo
    spaces: list[str]
    codex: CodexConfig


PROMPT = """You file short personal captures for one person. Reply with one JSON object only.

Fields:
- "shape": "task" if the text is something to do, otherwise "note".
- "space": one short lowercase label for where this belongs. Prefer one of the existing
  spaces when it fits; invent a new one only when none fits.
- "title": for a task, a short imperative title (max 80 chars). For a note, null.
- "due": for a task with a date, "YYYY-MM-DD" resolved from the current datetime;
  otherwise null.
- "remind_at": only when the text asks to be reminded at a particular time, an ISO 8601
  datetime with timezone offset; otherwise null.
- "confidence": 0 to 1, how sure you are about every field together. Be honest; below 0.85
  means a human should check.

Never rewrite or summarize the text itself. Only propose the fields. Do not run commands or
read files; everything you need is below.

Current datetime: {now} ({zone})
Existing spaces: {spaces}

Text:
{text}"""


def build_prompt(text: str, context: Context) -> str:
    spaces = ", ".join(context.spaces) if context.spaces else "(none yet)"
    return PROMPT.format(
        now=context.now.isoformat(), zone=context.zone.key, spaces=spaces, text=text
    )


def _normalize(proposal: Proposal, context: Context) -> Proposal:
    """Notes carry no task fields. Naive reminder times are in the user's zone; store UTC."""
    update: dict = {}
    if proposal.shape == "note":
        update.update(title=None, due=None, remind_at=None)
    elif proposal.remind_at is not None:
        ra = proposal.remind_at
        if ra.tzinfo is None:
            ra = ra.replace(tzinfo=context.zone)
        update["remind_at"] = ra.astimezone(UTC)
    return proposal.model_copy(update=update) if update else proposal


async def classify(text: str, context: Context) -> Proposal:
    try:
        data = await run_json(build_prompt(text, context), OUTPUT_SCHEMA, context.codex)
    except CodexError as e:
        raise ClassifyError(str(e)) from e
    try:
        proposal = Proposal.model_validate(data)
    except ValidationError as e:
        first = e.errors()[0]
        raise ClassifyError(f"invalid proposal: {first['loc']}: {first['msg']}") from e
    return _normalize(proposal, context)
