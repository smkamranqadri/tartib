"""The one AI function: classify(text, context) -> Proposal.

Runs the Codex CLI non-interactively with a JSON schema for the reply. Never touches storage.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import tempfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator


class ClassifyError(Exception):
    """The CLI is missing, failed, timed out, or returned something unusable."""


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


# What the CLI is told the reply must look like. Kept strict so the model cannot add fields.
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
    command: str  # e.g. "codex"; split with shlex
    model: str | None = None
    timeout: float = 120.0


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


def build_args(
    context: Context, workdir: Path, schema: Path, output: Path, prompt: str
) -> list[str]:
    args = shlex.split(context.command) + [
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        "--cd",
        str(workdir),
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
    ]
    if context.model:
        args += ["--model", context.model]
    args.append(prompt)
    return args


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
    with tempfile.TemporaryDirectory(prefix="tartib-classify-") as tmp:
        workdir = Path(tmp)
        schema = workdir / "schema.json"
        output = workdir / "reply.json"
        schema.write_text(json.dumps(OUTPUT_SCHEMA))
        args = build_args(context, workdir, schema, output, build_prompt(text, context))
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
        except (FileNotFoundError, PermissionError) as e:
            raise ClassifyError(f"cannot run {args[0]!r}: {e}") from e
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=context.timeout)
        except TimeoutError as e:
            proc.kill()
            await proc.wait()
            raise ClassifyError(f"timed out after {context.timeout:.0f}s") from e
        if proc.returncode != 0:
            tail = stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no output"]
            raise ClassifyError(f"exit {proc.returncode}: {tail[0][:300]}")
        try:
            raw = output.read_text()
        except FileNotFoundError as e:
            raise ClassifyError("no reply written") from e
    try:
        proposal = Proposal.model_validate(json.loads(raw))
    except ValidationError as e:
        first = e.errors()[0]
        raise ClassifyError(f"invalid proposal: {first['loc']}: {first['msg']}") from e
    except (TypeError, ValueError) as e:
        raise ClassifyError(f"unusable reply: {e}") from e
    return _normalize(proposal, context)
