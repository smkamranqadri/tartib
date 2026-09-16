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

1. Today: open tasks due today in `TARTIB_TZ`, plus starred open tasks, plus open tasks whose `remind_at` has passed. Overdue tasks count as due today. Below them, Recent: the newest 3 captures, extended to everything captured today (cap 20), each with its status, items, or answer.
2. Needs Attention: items in `stage=attention`, oldest first, with approve / edit / reject.
3. All: FTS5 search over `raw_text` and `title`, filter by space, shape, and status, newest first. Empty query lists everything. A chat-style Ask bar is pinned to the bottom; its answer opens above it. Item page `/items/{id}` shows the full excerpt, proposal, and inline edit; the space field is a select over `TARTIB_SPACES`.
4. Login: one password field. Shown when the session cookie is missing or invalid.

## Out of scope

Projects, tags, pomodoro, push notifications, an "ask" feature, a second AI adapter, offline capture queue, multi-user.
