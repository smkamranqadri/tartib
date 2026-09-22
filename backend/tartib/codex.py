"""The one AI transport: run a CLI non-interactively and get back a JSON object.

The Codex CLI is the only classifier; when it fails for any reason -- missing binary, non-zero
exit, usage limit, timeout, unusable reply -- the error goes back to the caller.
Both classify() and ask() go through here. Nothing in this module touches storage.
"""

from __future__ import annotations

import asyncio
import json
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path


class CodexError(Exception):
    """The CLI failed or returned something unusable.

    It carries whatever quota the stream reported: a call that failed *because* the window is
    exhausted is exactly when knowing how full it is matters most.
    """

    def __init__(self, *args, quota=None):
        super().__init__(*args)
        self.quota = quota


@dataclass(frozen=True)
class Usage:
    """What one turn consumed, as `turn.completed` reports it.

    `reasoning_output_tokens` is reported separately but is **already counted inside**
    `output_tokens` -- adding them would bill reasoning twice, which on a reasoning model is
    most of the bill. `billable()` is the only thing that should be priced.
    """

    input_tokens: int = 0
    cached_input_tokens: int = 0
    cache_write_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_output_tokens: int = 0
    total_tokens: int = 0

    @property
    def empty(self) -> bool:
        return self.total_tokens == 0 and self.input_tokens == 0 and self.output_tokens == 0

    def billable(self) -> tuple[int, int, int, int]:
        """(fresh input, cached input, cache writes, output). Fresh input excludes what was
        read from cache, because the two are priced differently and the CLI reports the cached
        part inside the input count."""
        fresh = max(self.input_tokens - self.cached_input_tokens, 0)
        return fresh, self.cached_input_tokens, self.cache_write_input_tokens, self.output_tokens


@dataclass(frozen=True)
class Quota:
    """How much of a rate-limit window is gone, as the CLI reports it on `token_count`.

    There are two windows -- a short one and a long one -- and the long one is what bites after
    a burst, which is why both are kept. The exact field shape is taken defensively: this was
    read off the binary, not off a live event, so anything missing stays None rather than
    becoming a confident zero.
    """

    used_percent: float | None = None
    window_minutes: int | None = None
    resets_at: str | None = None

    @property
    def known(self) -> bool:
        return self.used_percent is not None

    def as_dict(self) -> dict:
        return {
            "used_percent": self.used_percent,
            "window_minutes": self.window_minutes,
            "resets_at": self.resets_at,
        }


def _quota(raw: object) -> Quota:
    if not isinstance(raw, dict):
        return Quota()
    try:
        used = raw.get("used_percent")
        minutes = raw.get("window_minutes")
        return Quota(
            used_percent=float(used) if used is not None else None,
            window_minutes=int(minutes) if minutes is not None else None,
            resets_at=str(raw["resets_at"]) if raw.get("resets_at") is not None else None,
        )
    except (TypeError, ValueError):
        return Quota()


@dataclass(frozen=True)
class Reply:
    """A parsed reply and what it cost. `usage` is empty when the CLI reported none."""

    data: dict
    usage: Usage
    quota: tuple[Quota, Quota] = (Quota(), Quota())  # (primary, secondary)


@dataclass(frozen=True)
class CodexConfig:
    command: str  # e.g. "codex"; split with shlex
    model: str | None = None
    # Reasoning effort. Passed as a `-c` override because `--ignore-user-config` means the
    # user's own config.toml is deliberately not read -- a stray setting on a workstation must
    # not change how captures are filed.
    reasoning: str | None = None
    timeout: float = 120.0


def build_args(
    cfg: CodexConfig, workdir: Path, schema: Path, output: Path, prompt: str
) -> list[str]:
    """Codex argv. Kept as a public helper because tests assert on it."""
    return _codex_args(cfg.command, cfg.model, cfg.reasoning, workdir, schema, output, prompt)


def _codex_args(
    command: str,
    model: str | None,
    reasoning: str | None,
    workdir: Path,
    schema: Path,
    output: Path,
    prompt: str,
) -> list[str]:
    args = shlex.split(command) + [
        "exec",
        "--ephemeral",
        "--skip-git-repo-check",
        "--ignore-user-config",
        "--sandbox",
        "read-only",
        "--color",
        "never",
        # The turn as JSONL on stdout. It does not replace --output-last-message; the reply
        # still goes to the file. This is where the token counts and, importantly, the real
        # error text come from (slice 29).
        "--json",
        "--cd",
        str(workdir),
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
    ]
    if model:
        args += ["--model", model]
    if reasoning:
        args += ["-c", f"model_reasoning_effort={reasoning}"]
    args.append(prompt)
    return args


def parse_events(stdout: bytes) -> tuple[Usage, str | None, tuple[Quota, Quota]]:
    """Pull the usage and the failure message out of the JSONL stream.

    The message matters as much as the counts: before `--json`, CodexError took the last line
    of stderr-or-stdout, and with the stream on that line is a JSON blob. "You've hit your usage
    limit ... try again at 11:46 AM" is the text that makes a stalled run diagnosable, and it
    arrives here as an `error` event.
    """
    usage, message = Usage(), None
    quota = (Quota(), Quota())
    for line in stdout.decode(errors="replace").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        kind = event.get("type")
        if kind == "turn.completed" and isinstance(event.get("usage"), dict):
            u = event["usage"]
            usage = Usage(
                **{
                    f: int(u.get(f) or 0)
                    for f in (
                        "input_tokens",
                        "cached_input_tokens",
                        "cache_write_input_tokens",
                        "output_tokens",
                        "reasoning_output_tokens",
                        "total_tokens",
                    )
                }
            )
        elif kind == "error" and event.get("message"):
            message = str(event["message"])
        elif kind == "turn.failed" and not message:
            message = str((event.get("error") or {}).get("message") or "") or None
        elif kind == "token_count" and isinstance(event.get("rate_limits"), dict):
            limits = event["rate_limits"]
            quota = (_quota(limits.get("primary")), _quota(limits.get("secondary")))
    return usage, message, quota


async def _run(args: list[str], workdir: Path, timeout: float) -> tuple[Usage, tuple[Quota, Quota]]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,  # the CLI blocks reading a non-tty stdin
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise CodexError(f"cannot run {args[0]!r}: {e}") from e
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise CodexError(f"timed out after {timeout:.0f}s") from e
    usage, message, quota = parse_events(stdout)
    if proc.returncode != 0:
        if not message:
            # Nothing usable in the stream: fall back to what the process said, as before.
            text = (stderr or stdout).decode(errors="replace").strip()
            lines = [ln for ln in text.splitlines() if not ln.strip().startswith("{")]
            message = lines[-1] if lines else "no output"
        raise CodexError(f"exit {proc.returncode}: {message[:300]}", quota=quota)
    return usage, quota


def _parse_object(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise CodexError(f"unusable reply: {e}") from e
    if not isinstance(data, dict):
        raise CodexError("unusable reply: not a JSON object")
    return data


async def _run_codex(
    command: str,
    model: str | None,
    reasoning: str | None,
    prompt: str,
    schema: dict,
    timeout: float,
) -> Reply:
    with tempfile.TemporaryDirectory(prefix="tartib-codex-") as tmp:
        workdir = Path(tmp)
        schema_path = workdir / "schema.json"
        output = workdir / "reply.json"
        schema_path.write_text(json.dumps(schema))
        args = _codex_args(command, model, reasoning, workdir, schema_path, output, prompt)
        usage, quota = await _run(args, workdir, timeout)
        try:
            raw = output.read_text()
        except FileNotFoundError as e:
            raise CodexError("no reply written") from e
    return Reply(data=_parse_object(raw), usage=usage, quota=quota)


async def run_json(prompt: str, schema: dict, cfg: CodexConfig) -> Reply:
    """Run the CLI with `prompt`, constrained to `schema`. Returns the reply and what it cost."""
    return await _run_codex(
        cfg.command, cfg.model, cfg.reasoning, prompt, schema, cfg.timeout
    )
