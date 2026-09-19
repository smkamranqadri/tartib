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
    """The CLI failed or returned something unusable."""


@dataclass(frozen=True)
class CodexConfig:
    command: str  # e.g. "codex"; split with shlex
    model: str | None = None
    timeout: float = 120.0


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


async def _run(args: list[str], workdir: Path, timeout: float) -> None:
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
    if proc.returncode != 0:
        text = (stderr or stdout).decode(errors="replace").strip()
        tail = text.splitlines()[-1:] or ["no output"]
        raise CodexError(f"exit {proc.returncode}: {tail[0][:300]}")


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
        await _run(args, workdir, timeout)
        try:
            raw = output.read_text()
        except FileNotFoundError as e:
            raise CodexError("no reply written") from e
    return _parse_object(raw)


async def run_json(prompt: str, schema: dict, cfg: CodexConfig) -> dict:
    """Run the CLI with `prompt`, constrained to `schema`."""
    return await _run_codex(cfg.command, cfg.model, prompt, schema, cfg.timeout)
