"""The one AI transport: run a CLI non-interactively and get back a JSON object.

Primary is the Codex CLI. An optional fallback (the Claude CLI) is tried when the primary
fails for any reason: missing binary, non-zero exit, usage limit, timeout, unusable reply.
Both classify() and ask() go through here. Nothing in this module touches storage.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shlex
import tempfile
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("tartib.ai")


class CodexError(Exception):
    """The CLI (primary and, if configured, fallback) failed or returned something unusable."""


@dataclass(frozen=True)
class CodexConfig:
    command: str  # e.g. "codex"; split with shlex
    model: str | None = None
    timeout: float = 120.0
    fallback_command: str | None = None  # e.g. "claude"; None disables the fallback
    fallback_model: str | None = None


def dialect(command: str) -> str:
    """'claude' when any token of the command names it (binary or script), otherwise 'codex'."""
    names = [Path(p).name.lower() for p in shlex.split(command)]
    return "claude" if any("claude" in n for n in names) else "codex"


def build_args(
    cfg: CodexConfig, workdir: Path, schema: Path, output: Path, prompt: str
) -> list[str]:
    """Codex argv. Kept as a public helper because tests assert on it."""
    return _codex_args(cfg.command, cfg.model, workdir, schema, output, prompt)


def _codex_args(
    command: str, model: str | None, workdir: Path, schema: Path, output: Path, prompt: str
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
        "--cd",
        str(workdir),
        "--output-schema",
        str(schema),
        "--output-last-message",
        str(output),
    ]
    if model:
        args += ["--model", model]
    args.append(prompt)
    return args


def _claude_args(command: str, model: str | None, schema: dict, prompt: str) -> list[str]:
    args = shlex.split(command) + [
        "--print",
        "--no-session-persistence",
        "--output-format",
        "json",
        "--json-schema",
        json.dumps(schema),
        "--tools",
        "",
        "--max-turns",
        "3",  # structured output is a tool call, so the reply takes two turns
    ]
    if model:
        args += ["--model", model]
    args.append(prompt)
    return args


async def _run(
    args: list[str], workdir: Path, timeout: float, env: dict | None, *, check: bool = True
) -> tuple[int, bytes, bytes]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=asyncio.subprocess.DEVNULL,  # both CLIs block reading a non-tty stdin
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=workdir,
            env=env,
        )
    except (FileNotFoundError, PermissionError) as e:
        raise CodexError(f"cannot run {args[0]!r}: {e}") from e
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except TimeoutError as e:
        proc.kill()
        await proc.wait()
        raise CodexError(f"timed out after {timeout:.0f}s") from e
    if check and proc.returncode != 0:
        text = (stderr or stdout).decode(errors="replace").strip()
        tail = text.splitlines()[-1:] or ["no output"]
        raise CodexError(f"exit {proc.returncode}: {tail[0][:300]}")
    return proc.returncode or 0, stdout, stderr


def _parse_object(raw: str) -> dict:
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise CodexError(f"unusable reply: {e}") from e
    if not isinstance(data, dict):
        raise CodexError("unusable reply: not a JSON object")
    return data


async def _run_codex(
    command: str, model: str | None, prompt: str, schema: dict, timeout: float
) -> dict:
    with tempfile.TemporaryDirectory(prefix="tartib-codex-") as tmp:
        workdir = Path(tmp)
        schema_path = workdir / "schema.json"
        output = workdir / "reply.json"
        schema_path.write_text(json.dumps(schema))
        args = _codex_args(command, model, workdir, schema_path, output, prompt)
        await _run(args, workdir, timeout, None)
        try:
            raw = output.read_text()
        except FileNotFoundError as e:
            raise CodexError("no reply written") from e
    return _parse_object(raw)


async def _run_claude(
    command: str, model: str | None, prompt: str, schema: dict, timeout: float
) -> dict:
    # A nested-session marker from a parent Claude Code process would make the CLI refuse.
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}
    with tempfile.TemporaryDirectory(prefix="tartib-claude-") as tmp:
        code, stdout, stderr = await _run(
            _claude_args(command, model, schema, prompt), Path(tmp), timeout, env, check=False
        )
    try:
        envelope = _parse_object(stdout.decode(errors="replace"))
    except CodexError:
        if code != 0:
            tail = (stderr or stdout).decode(errors="replace").strip().splitlines()[-1:]
            raise CodexError(f"claude exit {code}: {(tail or ['no output'])[0][:300]}") from None
        raise
    if code != 0 or envelope.get("is_error"):
        detail = envelope.get("result") or envelope.get("subtype") or f"exit {code}"
        raise CodexError(f"claude error: {str(detail)[:300]}")
    structured = envelope.get("structured_output")
    if isinstance(structured, dict):
        return structured
    return _parse_object(str(envelope.get("result", "")))


async def run_json(prompt: str, schema: dict, cfg: CodexConfig) -> dict:
    """Run the primary CLI with `prompt`, constrained to `schema`; fall back if configured."""
    runners = {"codex": _run_codex, "claude": _run_claude}
    try:
        return await runners[dialect(cfg.command)](
            cfg.command, cfg.model, prompt, schema, cfg.timeout
        )
    except CodexError as primary:
        if not cfg.fallback_command:
            raise
        log.warning("primary AI failed (%s); trying fallback %s", primary, cfg.fallback_command)
        try:
            return await runners[dialect(cfg.fallback_command)](
                cfg.fallback_command, cfg.fallback_model, prompt, schema, cfg.timeout
            )
        except CodexError as fallback:
            raise CodexError(f"{primary}; fallback: {fallback}") from fallback
