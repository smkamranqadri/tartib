# Current

- Branch: `main`, local only.
- Task: none. Slice 9 complete and deployed 2026-09-17, plus a Fast-mode follow-up (Inbox headings, Back links).
- Command: `cd backend && uv run pytest -q` / `cd frontend && npm run build` / `docker compose up -d --build`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. Live container on http://localhost:8000.

## Proof (2026-09-17, slice 9)

- `uv run pytest -q`: 92 passed (recent keyset paging). `npm run typecheck`, `npm run build`: clean.
- Headless Chrome, desktop 1280 dark and phone 390, seeded 5 waiting + 124 captures: stars visible on Today rows without hover and toggle on click; Inbox shows 3 cards of 5 with "View all 5", one Enter approves exactly the first (one approve request), /attention/all shows all 4 remaining and approving there removes one; Recent 50 -> 100 -> 124 then Load more disappears; Spaces page has no chips and "+ New space" in the title row; a card opens /spaces/namazee with "← Spaces", the All/Tasks/Notes filter and "…" in the title row, Notes filter hides the tasks card; switching from namazee to coding never shows namazee's brief text; `/spaces?space=coding` redirects. No page errors.
- Deployed with `docker compose up -d --build`, health ok.
- Follow-up (headless): Inbox page head "Inbox", card head "Needs attention · 5 things to decide", one "Needs attention" on the page; Back from Recent returns to Inbox, Back on a direct /recent goes Home; Spaces has one heading.
