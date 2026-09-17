# Slice 9: inbox cards, spaces navigation, recent paging (approved 2026-09-17)

- Star always visible on task rows; edit on hover.
- Inbox: one "Needs attention" section with up to 3 approval cards (newest first); Enter approves the first; "View all" -> /attention/all with every waiting item as cards. Stale and Recent unchanged.
- Recent page pages by capture id ("Load more", 50 at a time).
- Spaces page: no chips; "+ New space" in the title row; cards link to /spaces/{name}. Space page: back button, title row with Tasks / Notes filter and "…" (rename, delete); scoped search; brief resets on space change.

## Status
- [x] backend paging
- [x] frontend
- [x] proof + deploy (2026-09-17, see kis/state/current.md)
