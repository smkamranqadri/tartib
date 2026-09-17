# Current

- Branch: `main`, local only.
- Task: none. Slice 5 UI simplification complete and deployed 2026-09-17, then adjusted on user feedback: Today merged into Home, chat bar back on every screen, Recent (3 captures + View all) under the list.
- Command: `cd frontend && npm run typecheck && npm run build` / `cd backend && uv run pytest -q` / `docker compose up -d --build`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. Live container on http://localhost:8000.

## Proof (2026-09-17, slice 5)

- `uv run pytest -q`: 75 passed. `uv run pytest -m eval`: 16 of 16 including "fix the login bug in tartib, and pray fajr on time tomorrow" -> 2 tasks, second due tomorrow.
- `npm run typecheck`, `npm run build`: clean.
- Headless Chrome against a host server with the steerable fake classifier, phone 390 (touch) and desktop 1280 dark:
  - Home: box focused on load, placeholder right, line "3 need attention · 2 due today"; type + Enter -> box empty and "Saved" toast in 39ms; outcome toast "Filed as task in home"; question capture -> answer under the box, toast "Answered".
  - Needs Attention: "1 of 3", Enter, Enter, Enter -> "All caught up."
  - Today: order starred, overdue, due today; max one chip per row; overdue row tinted; actions hidden until hover (desktop) or 500ms hold (touch); empty state "Nothing due. Capture something?" links to `/`.
  - `c` from Today lands on `/` with the box focused.
  - All: `/` focuses search; "what did I fix?" + Enter -> answer above results citing /items/4; typing clears it; Show done adds the done row; note collapsed to first line, expands on tap.
  - No page errors.
- `docker compose up -d --build`: health ok, `/` serves the new shell.

## Proof (2026-09-17, follow-up: merged page + chat bar)

- `npm run typecheck`, `npm run build`: clean.
- Headless Chrome, phone and desktop dark: Home shows the focused capture box and the 3 Today rows; `/today` redirects to `/`; chat bar visible on `/`, `/attention`, `/all`, and an item page; question through the bar returns the answer with a citation; `c` from All lands on `/` with the box focused. Recent shows 3 captures with View all -> /all. No page errors.

## Known gaps

- Reminders are not editable from the Needs Attention sentence; use the item page.
- "Show done" hides done tasks client-side, so a page of 50 can show fewer rows.
