# Contributing

Tartib is one person's capture system, published because the way it was built is worth reading. Issues and pull requests are welcome, with one caveat worth reading before you write any code.

## The constraints are the product

`kis/knowledge/rules.md` holds hard rules. They are not preferences and they are not up for a vote in a pull request. The important ones:

1. **The AI never rewrites your text.** A capture's `raw_text` is immutable. Classification proposes fields *around* the text, never instead of it.
2. **Capture never waits on AI.** `POST /api/capture` returns as soon as the row is stored.
3. **One set of prompts, run through CLIs as subprocesses.** No HTTP provider.
4. **No projects, no tags** — and Tartib does not nag. Three things may push: a reminder you set, one daily digest, and a session you started, when it ends. Nothing else, ever.
5. One password from env. No accounts, no signup.

A patch adding tags, projects, a pomodoro history screen, streaks, charts, or a fourth thing that pushes will be declined on principle rather than on taste. Each existing exception was argued for in writing, on the terms of the rule it bends, before any code was written — you can read those arguments in `kis/intent/` and in the commit messages. That route is open to you too, and it starts with a conversation in an issue, not a diff.

If something here is a bug, or is simply wrong, that is different and very welcome.

## Running it

```sh
cd backend && uv sync
TARTIB_PASSWORD=dev TARTIB_DB_PATH=./dev.db uv run uvicorn --factory tartib.main:create_app --reload

cd frontend && npm install && npm run dev      # proxies /api to :8000
```

## Before you open a pull request

```sh
cd backend  && uv run pytest -q && uv run ruff check .
cd frontend && npm run typecheck && npm run build
```

`uv run pytest -m eval` additionally runs 22 captures through the real Codex CLI and needs a `codex login`. It is not required for a pull request.

Tests drive a fake Codex script as a real subprocess, so the default suite never needs `codex` itself and never reaches the network.

## House style

- **Prove it before you call it done.** Test output, a build, a real run, a screenshot for anything visible. "It should work" is not a verification, and the commit message is where the proof goes.
- **One component owns one pattern.** `Row` is the only place a list row is drawn; `Menu` is the only "…"; `Card`, `PageHead`, `Status` likewise. If a screen writes its own markup for something that already exists, that is the bug.
- **`store.py` is the single write path** for filing. The runner, approve, reject and PATCH all go through it.
- **Migrations are numbered SQL files** applied at startup, and they carry a comment explaining what went wrong that made them necessary.
- **Say why, not what.** The diff already says what changed. Comments and commit messages are for the reason, especially when the obvious approach was tried first and did not work.
- No modals. No dialogs. If something needs answering, it is asked in place.

## Project memory

`kis/` is checked in: `knowledge/` is what is true, `intent/` is what was planned and why, `state/` is where things stand right now. It is maintained by the [KIS](.agents/skills/kis/SKILL.md) loop.

If you change how something works, the matching KIS layer changes in the same commit. A fact belongs in exactly one of the three.
