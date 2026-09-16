"""The one AI function: classify(text, context) -> Proposal.

Calls an OpenAI-compatible chat completions endpoint. Never touches storage.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ClassifyError(Exception):
    """The endpoint is unavailable, unconfigured, or returned something unusable."""


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


@dataclass(frozen=True)
class Context:
    now: datetime  # timezone-aware, in the user's zone
    zone: ZoneInfo
    spaces: list[str]
    base_url: str
    model: str
    api_key: str | None = None
    timeout: float = 60.0


SYSTEM_PROMPT = """You file short personal captures for one person. Reply with one JSON object only.

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

Never rewrite or summarize the text itself. Only propose the fields."""


def _user_prompt(text: str, context: Context) -> str:
    spaces = ", ".join(context.spaces) if context.spaces else "(none yet)"
    return (
        f"Current datetime: {context.now.isoformat()} ({context.zone.key})\n"
        f"Existing spaces: {spaces}\n\n"
        f"Text:\n{text}"
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
    payload = {
        "model": context.model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _user_prompt(text, context)},
        ],
    }
    headers = {"Authorization": f"Bearer {context.api_key}"} if context.api_key else {}
    try:
        async with httpx.AsyncClient(timeout=context.timeout) as client:
            resp = await client.post(
                f"{context.base_url}/chat/completions", json=payload, headers=headers
            )
        resp.raise_for_status()
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
        proposal = Proposal.model_validate(data)
    except httpx.HTTPError as e:
        raise ClassifyError(f"endpoint error: {e}") from e
    except ValidationError as e:
        first = e.errors()[0]
        raise ClassifyError(f"invalid proposal: {first['loc']}: {first['msg']}") from e
    except (KeyError, IndexError, TypeError, ValueError) as e:
        raise ClassifyError(f"unusable reply: {e}") from e
    return _normalize(proposal, context)
