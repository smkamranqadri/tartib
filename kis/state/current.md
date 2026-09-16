# Current

- Branch: `main`, local only, no remote.
- Task: none. v0.1 scaffold complete through Phase 4 (2026-09-17).
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d`.
- Blocker: none.
- Next: user decides. Candidates in `kis/intent/ARCHITECTURE.md`. First real use needs a `.env` with an AI endpoint to exercise auto-filing outside tests.

## Proof (2026-09-17)

- `uv run pytest -q`: 38 passed.
- `uv run ruff check .`: clean.
- `npm run typecheck` and `npm run build`: clean.
- `docker compose up`: health ok, capture returned 201 in 15ms with AI unset, item parked in Needs Attention with "AI not configured".
- Container restart kept data. `docker stats`: 36.8MiB of the 512MiB limit.
- Headless Chrome (playwright-core, channel chrome): login, wrong-password error, Today rules, done toggle, capture from the box, edit-and-approve, reject, search, space/shape filters, inline edit in All, dark mode at 1280px, phone width 390px. Service worker controls the page after reload; manifest valid.

## Known gaps

- Auto-file path is covered by tests with a mocked endpoint only. Not yet run against a real model.
- Image is 524MB (see intent follow-ups).
