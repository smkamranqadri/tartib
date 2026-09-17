# Current

- Branch: `main`, local only.
- Task: none. Slice 7 dashboard restyle complete and deployed 2026-09-17.
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d --build`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. Live container on http://localhost:8000.

## Proof (2026-09-17, slice 7)

- `uv run pytest -q`: 85 passed (config endpoint, stale tasks, recent = 10). `npm run typecheck`, `npm run build`: clean.
- Headless Chrome, desktop 1280 dark and phone 390, seeded fake classifier, fake speech engine injected: nav Home · Inbox · Search · Settings; Home title is today's date, two columns on desktop and one on phone, Today count 2 matches rows, Needs attention count 4 = 3 queued + 1 stale, meta lines "coding · just now", due at the right; mic button present and dictation fills the box; capture from the header on Search toasts "Filed as task in home"; Search shows space cards, a namazee chip shows its brief, "?" asks scoped to namazee, results group by space, shape chip lands in the URL; `/spaces/namazee` and `/all` redirect; Inbox shows "4 things to decide", the stale task under Stale tasks only, "1 of 3", Enter ×3 clears the queue; Settings shows theme, classifier, timezone Asia/Karachi, spaces, and sign out returns to login. No page errors.
- Deployed with `docker compose up -d --build`, health ok.

## Known gaps

- Real dictation depends on the browser; verified with an injected engine only.
- Stale threshold fixed at 14 days.
