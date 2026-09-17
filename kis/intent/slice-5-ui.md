# Slice 5: UI simplification (approved 2026-09-17)

No backend changes except the eval fixture. Capture box lives only on Home; `c` jumps there.

## Scope

1. Home `/`: large centered capture box, autofocus, "What's on your mind?". One line under it: "N need attention · M due today" as links. On save the box clears at once and a toast says "Saved", then updates to the outcome ("Filed as task in namazee", "Needs your look", "Filed 2 tasks · 1 needs your look", "Answered"). Question answers show under the box. No Recent list.
2. Today: flat list from the unchanged endpoint, ordered starred, overdue, due today, reminders. Row = checkbox, title, at most one chip (overdue or a time). Overdue tinted. Hover / long-press reveals star and edit. Empty: "Nothing due. Capture something?" -> `/`.
3. Needs Attention: one card at a time, header "k of n". Raw text, then the proposal as a sentence with tappable shape, title, space, due. Approve (Enter), Not now (to the back of the queue), "…" with Reject and Open. Empty: "All caught up."
4. All: search + space dropdown + "Show done" toggle (client-side). Minimal rows; notes show the first line, expand on tap. Enter with trailing "?" or Cmd/Ctrl+Enter runs ask in the selected space; answer above results, cleared on the next search. `/` focuses search.
5. Global: AskBar gone, per-screen capture box gone, nav gains Home. Timestamps relative and hover-only. One chip per row. `c` -> Home with the box focused.
6. Eval fixture: "fix the login bug in tartib, and pray fajr on time tomorrow" -> 2 tasks, second due tomorrow.

## Acceptance

- Open `/`, type, Enter: box empty and "Saved" visible within 2s; outcome toast when classification ends.
- Needs Attention with 3 items that have a space: Enter, Enter, Enter clears it.
- Today rows: one chip max, overdue tinted, hover reveals star and edit.
- All: question + Enter shows an answer above results; typing clears it; Show done works; `/` focuses search.
- `c` from Today lands on `/` focused.
- `pytest -m eval`: 16 of 16.

## Status

- [x] frontend
- [x] eval fixture
- [x] proof (2026-09-17, see kis/state/current.md)
