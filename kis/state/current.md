# Current

- Branch: `main`, local only, working tree clean.
- Task: slice 11, push reminders. Plan approved 2026-09-17 in `kis/intent/slice-11-reminders.md`. Not started.
- Run it: `docker compose up -d --build`, then http://localhost:8000. Password in `.env`.
- Verify: `cd backend && uv run pytest -q` (92 passed) and `uv run pytest -m eval` (16 real-Codex fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Blocker: none. The phone proof needs a temporary HTTPS tunnel; Web Push will not work over `http://localhost` from a phone.
  Nothing is installed yet: `brew install cloudflared`, then `cloudflared tunnel --url http://localhost:8000`.
- After 11: slices 12 to 14 are approved but unplanned; they are listed in `kis/intent/backlog.md`.
- Next: implement slice 11 in three steps, in this order: migration 0005 plus the subscriptions table and the 60s loop, then `sw.js` and the Settings toggle, then proof and deploy.

## Proof (2026-09-17)

Backend 92 tests pass; frontend typechecks and builds. Every route was driven headlessly at 390px and 1280px with the fake classifier, and the live container was rebuilt and answered `/api/health`. Real Codex was exercised on the host for classification, briefs, and ask. Slice 11 has no proof yet.

## Known gaps

- The Claude fallback inside Docker needs `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`; without it a Codex outage still parks captures in the Inbox.
- A brief refreshes only when an item is added or removed, or on its refresh icon.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
