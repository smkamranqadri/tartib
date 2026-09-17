# Current

- Branch: `main`, local only.
- Task: none. Slice 6 Spaces view complete and deployed 2026-09-17.
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d --build`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. Live container on http://localhost:8000. Backups in the session scratchpad `backup/` (pre-slice4, pre-reclassify, pre-slice6).

## Proof (2026-09-17, slice 6)

- `uv run pytest -q`: 83 passed (updated_at triggers, summary counts and order, brief cache hit/miss/refresh, brief input rows, empty and unknown space, errors, active space, migration 0003 backfill).
- `npm run typecheck`, `npm run build`: clean.
- Headless Chrome, desktop dark, seeded fake classifier: nav Today · Attention · Spaces; cards with real counts sorted by activity, overdue dot on namazee, muted Unfiled; no chat bar on Spaces; grouped search; namazee page brief fresh with 3 cited links, tasks ordered overdue-first, notes; reopen served from cache (0 Codex calls); Notes collapse survives reload; capturing a namazee task from Home -> home line "1 need attention · 1 due today · namazee active", reopening regenerates the brief (1 call) and lists the new task; scoped "?" ask answered from namazee only; refresh icon present. Phone layout checked.
- Live: backup taken, migration 0003 applied on the volume, summary shows 7 spaces with counts, real Codex briefs for namazee (4 lines, 8 cited) and coding (4 lines, 9 cited) in about 14s each, second namazee call `fresh: false`.

## Known gaps

- Briefs are as good as Codex's reading; the coding brief quoted a note's numbers verbatim. Refresh regenerates.
- Brief text can run to 4 to 5 lines of prose; "Max 5 lines" is honoured by the prompt, not enforced.
