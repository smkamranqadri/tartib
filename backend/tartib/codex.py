"""The one AI transport: run the Codex CLI non-interactively and get back a JSON object.

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
    """The CLI is missing, failed, timed out, or returned something unusable."""


@dataclass(frozen=True)
class CodexConfig:
    command: str  # e.g. "codex"; split with shlex
    model: str | None = None
    timeout: float = 120.0


def build_args(
    cfg: CodexConfig, workdir: Path, schema: Path, output: Path, prompt: str
) -> list[str]:
    args = shlex.split(cfg.command) + [
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
    if cfg.model:
        args += ["--model", cfg.model]
    args.append(prompt)
    return args


async def run_json(prompt: str, schema: dict, cfg: CodexConfig) -> dict:
    """Run Codex with `prompt`, constrained to `schema`, and return the parsed reply."""
    with tempfile.TemporaryDirectory(prefix="tartib-codex-") as tmp:
        workdir = Path(tmp)
        schema_path = workdir / "schema.json"
        output = workdir / "reply.json"
        schema_path.write_text(json.dumps(schema))
        args = build_args(cfg, workdir, schema_path, output, prompt)
        try:
            proc = await asyncio.create_subprocess_exec(
                *args,
                stdin=asyncio.subprocess.DEVNULL,  # Codex blocks reading a non-tty stdin
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                cwd=workdir,
            )
        except (FileNotFoundError, PermissionError) as e:
            raise CodexError(f"cannot run {args[0]!r}: {e}") from e
        try:
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=cfg.timeout)
        except TimeoutError as e:
            proc.kill()
            await proc.wait()
            raise CodexError(f"timed out after {cfg.timeout:.0f}s") from e
        if proc.returncode != 0:
            tail = stderr.decode(errors="replace").strip().splitlines()[-1:] or ["no output"]
            raise CodexError(f"exit {proc.returncode}: {tail[0][:300]}")
        try:
            raw = output.read_text()
        except FileNotFoundError as e:
            raise CodexError("no reply written") from e
    try:
        data = json.loads(raw)
    except ValueError as e:
        raise CodexError(f"unusable reply: {e}") from e
    if not isinstance(data, dict):
        raise CodexError("unusable reply: not a JSON object")
    return data
