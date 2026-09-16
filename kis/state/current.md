# Current

- Branch: `main`, local only.
- Task: none. Slice 4 (classifier fixes, absorbing slice 3) complete 2026-09-17. Plan: `kis/intent/slice-4-classifier.md`.
- Command: `cd backend && uv run pytest -q` / `uv run pytest -m eval` / `cd frontend && npm run build` / `docker compose up -d --build`.
- Blocker: none in code. Codex usage limit on the ChatGPT account was exhausted at the end of the deploy; captures made until it resets land in Needs Attention with the error.
- Next: user decides. Live container on http://localhost:8000 runs the new image on the migrated volume. Backup of the pre-migration DB: scratchpad `backup/tartib-pre-slice4.db` (session-local; copy it out if wanted).

## Proof (2026-09-17, slice 4)

- `uv run pytest -q`: 67 passed (fake Codex subprocess; includes v1 -> v2 migration and space reconciliation). `ruff`: clean. `npm run typecheck` and `build`: clean.
- `uv run pytest -m eval`: 15 of 15 fixtures pass against real Codex (3 multi-item, 2 questions, 2 no-space, 2 verb-less tasks, 1 timed reminder, 5 plain), 19s.
- Host smoke with real Codex: "A, B, and C" -> 3 tasks with own excerpts; two-fact sentence -> 2 notes; "Ping Sara re: Thursday" -> task, parked; question -> answered citing the right item; "remind me at 6pm" -> 13:00Z.
- Headless Chrome at 390px and 1280px: split capture shows 3 chips in Recent within the filing poll; question capture shows the answer panel under the box with a link to the item; space select lists all configured spaces; no-space item shows File… with Approve disabled until a space is picked; Reject keeps the item; ask bar in viewport over 36 rows with the last row reachable; answer opens and closes above it; status filter present.
- Live migration: backup taken, dry run on a copy (22 items -> 22 captures + 22 items, 7 inbox -> attention, integrity ok), then `docker compose up -d --build` on the real volume. `.env` TARTIB_SPACES set to the 7 spaces actually in use so nothing filed was disturbed. Health ok, spaces from config, 7 waiting, search works.
- Live capture after deploy: Codex returned "usage limit" -> capture status error, one note in Needs Attention with the message. Fallback path verified in production.

## Known gaps

- No retry for captures that failed on a Codex outage or usage limit; they wait for a human.
- Container memory read 300MiB right after a Codex call (node process + page cache); idle baseline earlier was 42MiB.
