# Current

- Branch: `main`, local only.
- Task: none. Slice 2 (retrieval) complete 2026-09-17. Plan and checklist in `kis/intent/slice-2-retrieval.md`.
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d`.
- Blocker: none.
- Next: user decides. The compose container on http://localhost:8000 still runs the pre-slice image; `docker compose up -d --build` picks up the new UI and ask endpoint.

## Proof (2026-09-17, slice 2)

- `uv run pytest -q`: 52 passed. `uv run ruff check .`: clean. `npm run typecheck` and `npm run build`: clean.
- Acceptance, host with real Codex: 10 notes across 10 spaces captured and classified in 90s (8 auto-filed, 2 parked at 0.81 and 0.82). Every note found by one distinctive word via `/api/items?q=`. Four "what did I decide about X?" questions answered correctly, each citing exactly the right item id, about 7s each. Space-scoped ask with an empty space returned the fixed empty shape.
- Headless Chrome: dark theme toggle, search narrows to one row, status filter, ask in the UI renders the answer and a cited link, link opens `/items/2` with full raw text and proposal, inline edit of space saves and updates the header. Phone width 390px checked for All, item page, Today.

## Known gaps

- Retrieval is keyword only. A question that names a concept the note does not literally contain (e.g. "database" for a note that says "SQLite") falls back to the 20 most recent items in the space. Fine at personal scale; noted in Intent.
- Ask is synchronous; the request waits for Codex.
