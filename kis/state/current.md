# Current

- Branch: `main`, local only.
- Task: none. Slice 10 consistency pass complete and deployed 2026-09-17.
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run typecheck && npm run build` / `docker compose up -d --build`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. Live container on http://localhost:8000.

## Proof (2026-09-17, slice 10)

- `npm run typecheck`, `npm run build`: clean. Backend untouched.
- Single ownership, by grep, all zero outside their component: row markup, menu markup, "Yes, delete", the name form, `section-toggle`, `.ask-btn`, `formatCreated`, hand-rolled `crumbs`.
- Headless Chrome, desktop 1280 dark and phone 390: all eight routes render exactly the eyebrow, title, and subtitle in the SPEC table; `/attention`, `/attention/all`, `/recent`, `/today`, `/search` redirect; the Inbox pill stays active on all three inbox routes; the "…" menu on Inbox, the space page, and the item page opens and closes on both outside click and Escape; the item page's space name opens that space; Home's Today rows carry stars and its Needs attention rows are ItemRows. No page errors.
- Deployed with `docker compose up -d --build`, health ok.

## Known gaps

- Real dictation still depends on the browser.
- Brief only refreshes when an item is added or removed, or on the refresh icon.
