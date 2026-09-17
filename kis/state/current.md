# Current

- Branch: `main`, local only.
- Task: none. Slice 4 plus its same-day follow-up (Recent = 3, global ask bar, Claude CLI fallback) complete and deployed 2026-09-17.
- Command: `cd backend && uv run pytest -q` / `uv run pytest -m eval` / `cd frontend && npm run build` / `docker compose up -d --build`.
- Blocker: none in code. Inside Docker the Claude fallback needs `CLAUDE_CODE_OAUTH_TOKEN` in `.env` (from `claude setup-token` on the host); until then a Codex failure in the container still ends in Needs Attention.
- Next: user decides. Live container on http://localhost:8000. Pre-slice-4 DB backup in the session scratchpad `backup/tartib-pre-slice4.db`.

## Proof (2026-09-17, follow-up)

- `uv run pytest -q`: 72 passed (fake Codex and fake Claude as real subprocesses; fallback used only when the primary fails; both-fail error names both; questions and /api/ask go through the fallback too; CLAUDECODE stripped).
- Host, Codex deliberately missing, real Claude CLI (haiku): "A, B, and C" -> 3 tasks with excerpts in 31s including a question capture answered with the right citation and correct open status.
- Headless Chrome, phone 390 and desktop 1280: ask bar present on Today, Needs Attention, All, and an item page; bar x/width equals the app column on both sizes; Recent shows only the newest captures; no page errors.
- `docker compose up -d --build`: health `{"ok":true,"ai":true,"fallback":true}`, codex 0.153.2 and Claude Code 2.1.274 present in the container, image 1.46GB, live data intact.

## Known gaps

- No retry for captures that failed while both CLIs were unavailable; they wait for a human.
- Claude fallback in Docker is unauthenticated until the token is set.
