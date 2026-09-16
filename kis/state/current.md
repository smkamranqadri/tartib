# Current

- Branch: `main`, local only, no remote.
- Task: none. v0.1 complete; classifier switched from HTTP endpoint to Codex CLI (2026-09-17).
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d`.
- Blocker: none.
- Next: user decides. Compose stack is running on http://localhost:8000 (password in `.env`) with seeded sample items for review. Candidates in `kis/intent/ARCHITECTURE.md`.

## Proof (2026-09-17)

- `uv run pytest -q`: 41 passed (fake Codex subprocess). `uv run ruff check .`: clean.
- `npm run typecheck` and `npm run build`: clean.
- Host, real Codex: 3 captures classified in 33s. Dentist -> task/health/due/reminder at 0.99, filed. "hmm" -> 0.72, Needs Attention. Idea -> note/ideas 0.98, filed.
- Docker, real Codex via mounted ~/.codex: "book flights to Lahore for the 3rd of October" -> task/travel/due 2026-10-03 at 0.94, filed in 8s.
- `docker stats`: 41.7MiB of 512MiB. Image 1.13GB (Node + Codex added).
- Container restart kept data (earlier run). Headless Chrome UI checks (earlier run) unchanged by this switch.

## Known gaps

- Image is 1.13GB. Runtime memory is tiny; size is cosmetic but noted in Intent.
- Codex classification is serial, about 8 to 12s per item.
