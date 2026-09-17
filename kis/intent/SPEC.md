# Tartib SPEC

What the product does. How it is built lives in `kis/knowledge/technical.md`. Hard rules live in `kis/knowledge/rules.md`.

Status: v0.1 built and verified 2026-09-17. Every section below is implemented.

## Capture and Item

A capture is what the user typed, stored once: `id`, `raw_text` (immutable), `source` (web | api | migrated), `created_at`, `status` (pending | done | error), `error`, `answer`.

An item is classifier output. One capture produces zero or more items.

- Shared: `id`, `capture_id`, `raw_text` (starts as the verbatim excerpt this item came from; editable by the user once filed), `space` (one of `TARTIB_SPACES`, or null while waiting), `shape` (`task` | `note`), `stage` (`attention` | `filed`), `created_at`.
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
- Delete (item page, confirmed inline): removes the item; the capture stays.

## Editing

Any filed item's `space`, `shape`, `title`, `due`, `remind_at`, `starred`, and `status` can be changed. `raw_text` cannot.

## Screens (dashboard layout, 2026-09-17)

Shell: brand "Tartib ترتیب", pill nav Home · Inbox · Spaces · Settings with icons, and a capture bar under the header on every screen (auto-growing box, mic when the browser supports on-device speech, Add). Enter or Add saves, Shift+Enter adds a line; the box clears at once, a toast says "Saved" then the outcome; a question capture navigates to Home and shows its answer. Chat bar on Home and Inbox only. `c` focuses capture anywhere; `/` focuses search on Search.

1. Home `/`: eyebrow DASHBOARD, title = today's date. Two columns from 900px, one below. Left: Today (open tasks due today or overdue, starred, passed reminders; starred first; count) and Recent (last 3 captures, "View all" -> `/recent`). Right: Needs attention (top 3 of queue then stale, "View all", and a line naming the most recently touched space). On phone the order is Today, Needs attention, Recent.
2. Inbox `/attention`: title "Needs attention", "N things to decide". Awaiting approval = the one-card queue ("k of n"; Enter approves, Not now rotates, "…" holds Reject and Open). Waiting = every queued item, tap to bring it forward. Stale tasks = open filed tasks untouched 14+ days. Recent = last 3, "View all".
3. Spaces `/spaces`: title "Spaces" (or the selected space). Search-or-ask field (Ask button once there is text; trailing "?" or Cmd/Ctrl+Enter). Chips: All spaces + each space; Any shape / Tasks / Notes; state in the URL. No query + All spaces -> space cards (name, "4 open · 12 notes", last activity, overdue dot; Unfiled muted, links to Inbox). No query + a space -> that space's Brief (cached, refresh), Tasks (Show done), Notes, collapsible and remembered per space. Query -> results grouped by space. `/spaces`, `/spaces/{name}`, `/all` redirect here.
4. Settings `/settings`: Appearance (theme), Classifier (Codex on/off, fallback, threshold), Device (voice capture, timezone, installed), Spaces (configured list), Account (sign out). Read-only except theme and sign out.
5. Item page `/items/{id}`: the item's text (editable via "…" > Edit text or double-click), status chips, "File it" (while waiting) or "Edit" (filed) and "Proposal" as accordions, open while waiting and closed once filed; the Proposal shows the original capture text when it differs. "…" also holds Delete with an inline confirm.
6. Recent `/recent`: the last 50 captures, newest first.
7. Login: one password field.

Rows everywhere: leading checkbox (filed tasks) or icon, title (links to the item page for tasks and notes), muted meta "space · 2h ago" (or "needs attention · 70%"), "due Fri, Sep 18" at the right for dated tasks, overdue rows tinted, hover or long-press reveals star and edit.

## Out of scope

Projects, tags, pomodoro, push notifications, an "ask" feature, a second AI adapter, offline capture queue, multi-user.
