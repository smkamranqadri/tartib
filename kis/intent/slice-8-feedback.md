# Slice 8: feedback round (approved 2026-09-17)

## Decisions
- Rule 1 narrowed: the AI never rewrites text; captures stay immutable; a filed item's text is the user's to edit.
- Spaces live in a `spaces` table, seeded once from `TARTIB_SPACES`, managed from the Spaces page. Delete only when empty. Rename cascades to items and briefs.
- Brief cache key = item count + newest item id in the space. Done/star/edit do not regenerate; refresh does.
- Delete removes the item only; the capture stays.
- Note titles open the item page. Inline expand removed.
- Recent = 3 on Home and Inbox, "View all" -> /recent (last 50 captures).
- Inbox = queue card + Waiting list (tap to bring forward) + Stale + Recent.
- Nav Home · Inbox · Spaces · Settings. /search -> /spaces.
- Capture bar is an auto-growing textarea; Enter saves, Shift+Enter newline.
- Item page: text editable; "File it"/"Edit" and "Proposal" are accordions, open while waiting, closed once filed; original capture text shown when it differs; "…" with Delete.

## Status
- [ ] phase 1 backend
- [ ] phase 2 frontend
- [ ] phase 3 proof + live migration + deploy
