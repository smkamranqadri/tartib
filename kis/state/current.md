# Current

- Branch: `main`, local only, working tree clean.
- Task: none. Slice 10 was the last one, deployed 2026-09-17.
- Run it: `docker compose up -d --build`, then http://localhost:8000. Password in `.env`.
- Verify: `cd backend && uv run pytest -q` (92 passed) and `uv run pytest -m eval` (16 real-Codex fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Blocker: none.
- Next: user decides. `kis/intent/backlog.md` holds the unscheduled candidates.

## Proof (2026-09-17)

Backend 92 tests pass; frontend typechecks and builds. Every route was driven headlessly at 390px and 1280px with the fake classifier, and the live container was rebuilt and answered `/api/health`. Real Codex was exercised on the host for classification, briefs, and ask.

## Known gaps

- The Claude fallback inside Docker needs `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`; without it a Codex outage still parks captures in the Inbox.
- A brief refreshes only when an item is added or removed, or on its refresh icon.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
