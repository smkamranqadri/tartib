# Slice 6: Spaces view (approved 2026-09-17)

Replaces All. Nav stays Today · Attention · Spaces (Home remains capture + today + recent).

## Decisions
- `items.updated_at`, trigger-maintained, internal. Backfilled from classified_at or created_at.
- `briefs` table caches one AI brief per space, keyed by fingerprint = (item count, max updated_at). Regenerated on mismatch or explicit refresh. Never an item, never editable.
- Brief input = every open task in the space + 15 newest notes (cap 30), through the ask prompt with the fixed question, scoped to the space. Empty space -> "Nothing here yet." without a Codex call.
- Unfiled card = space NULL items; links to Attention; no brief.
- /spaces search = items search grouped by space client-side. Space page search is scoped; "?" or Cmd/Ctrl+Enter asks scoped. Chat bar hidden on /spaces routes.

## Acceptance
- /spaces: one card per configured space + Unfiled, real counts, sorted by activity, overdue dot.
- namazee page: brief of at most 5 lines naming its open tasks, "Updated just now", cited items.
- Add a namazee task, reopen -> brief regenerates; reopen unchanged -> cache, no Codex call.
- Marking done bumps updated_at and moves the space up.
- Scoped "?" search answers from that space only. Collapse state per space survives reload.

## Status
- [x] backend
- [x] frontend
- [x] proof (2026-09-17, see kis/state/current.md)
