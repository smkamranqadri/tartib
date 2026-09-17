# Tartib SPEC

What the product does. How it is built lives in `kis/knowledge/technical.md`. Hard rules live in `kis/knowledge/rules.md`.

Status: v0.1 built and verified 2026-09-17. Every section below is implemented.

## Capture and Item

A capture is what the user typed, stored once: `id`, `raw_text` (immutable), `source` (web | api | migrated), `created_at`, `status` (pending | done | error), `error`, `answer`.

An item is classifier output. One capture produces zero or more items.

- Shared: `id`, `capture_id`, `raw_text` (the verbatim excerpt this item came from, immutable), `space` (one of `TARTIB_SPACES`, or null while waiting), `shape` (`task` | `note`), `stage` (`attention` | `filed`), `created_at`.
- Task fields: `title`, `due?` (date), `remind_at?` (datetime), `starred` (bool), `status` (`open` | `done`).
- Note: no extra fields. Display uses `raw_text`.
- Each item keeps its `proposal` and `proposal_error`, even after filing, so auto-filed decisions stay inspectable.
- A filed item always has a space (database check).

## Capture

Input box at the top of every screen, or `POST /api/capture {"text": "..."}`. The capture is stored and `201 {id}` returns immediately. `GET /api/captures/{id}` reports status, items, and answer; the PWA polls it after each capture.

## Classify

A background call to `classify(text, context)` returns a list of proposals `{text, shape, space, title, due, remind_at, confidence}`, one per independent item in the capture. Context: current datetime in `TARTIB_TZ` and the configured spaces.

- shape `question`: no item. The runner answers it from existing items and stores the answer on the capture.
- space outside the configured list: null, confidence capped at 0.6.
- space null or `confidence < TARTIB_AUTOFILE_CONFIDENCE` (default 0.85): `stage=attention`.
- otherwise: `stage=filed`.
- classifier off, CLI missing, failing, timing out, or invalid output: one note with space null in `attention`, `proposal_error` set, capture `status=error`.
- on startup, pending captures are re-queued, so a restart mid-classify loses nothing.

## Needs Attention decisions

- Approve: file with the stored proposal, overridden by any fields in the request. A space is required.
- Reject: discard the proposal (note, space null, dates cleared). The item stays in `attention`. Nothing is deleted.

## Editing

Any filed item's `space`, `shape`, `title`, `due`, `remind_at`, `starred`, and `status` can be changed. `raw_text` cannot.

## Screens

1. Today `/` (one page, changed 2026-09-17): the capture box, focused on load, placeholder "What's on your mind?"; a line "N need attention · M due today · {space} active" (the last links to the most recently touched space); then today's flat list from the Today endpoint (due today or overdue, starred, passed reminders), ordered starred, overdue, due today, reminders. Row = checkbox, title, at most one chip (overdue or a time). Overdue rows tinted. Hover or long-press reveals star, edit, and the relative time. Empty list: "Nothing due today." Under the list, Recent: the newest 3 captures with a "View all" link to All. Saving clears the box at once and shows a toast: "Saved", then the outcome ("Filed as task in namazee", "Needs your look", "Filed 2 tasks · 1 needs your look", "Answered"). A question capture shows its answer under the box. `/today` redirects here.
2. Chat bar: pinned to the bottom of every screen except All, as wide as the app column, translucent over the content. Question in, answer above it with linked items. On All the search field is search-or-ask: an Ask button appears once there is text; Enter with a trailing "?" or Cmd/Ctrl+Enter also asks.
3. Needs Attention: one card at a time, header "k of n". Raw text, then the proposal as a sentence with tappable shape, title, space, and due. Approve (Enter) files it; Not now sends it to the back of the queue; "…" holds Reject (discard proposal) and Open. Empty: "All caught up."
4. Spaces `/spaces` (replaced All, 2026-09-17): a search-or-ask field across all spaces (results grouped by space, Unfiled last), then one card per configured space plus a muted Unfiled card: name, "4 open · 12 notes", last activity, a red dot when an open task is overdue. Sorted by last activity; spaces with none keep config order at the end. Unfiled links to Attention.
   Space page `/spaces/{name}`: scoped search-or-ask; Brief (AI, read-only, cached until an item in the space changes, "Updated 2h ago", refresh icon); Tasks (open, starred then due, Show done at the bottom); Notes (newest, first line, expand). Tasks and Notes collapse, remembered per space. `/all` redirects here.
5. Item page `/items/{id}`: full text, proposal, inline edit; space is a select over `TARTIB_SPACES`.
6. Login: one password field.

Global: the capture box lives only on Today; the chat bar is everywhere except the Spaces screens, where the search field asks. Nav: Today · Attention · Spaces. Timestamps are relative and hover-only. One chip per row. `c` anywhere goes to Home with the box focused.

## Out of scope

Projects, tags, pomodoro, push notifications, an "ask" feature, a second AI adapter, offline capture queue, multi-user.
