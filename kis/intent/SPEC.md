# Tartib SPEC

What the product does. How it is built lives in `ARCHITECTURE.md`. Hard rules live in `kis/knowledge/rules.md`.

## Item

Every capture is one Item.

- Shared: `id`, `raw_text` (immutable), `space` (free text, default `inbox`), `shape` (`task` | `note`), `stage`, `created_at`.
- `stage` is the classification lifecycle: `inbox` (just captured) -> `attention` (proposal needs a decision) -> `filed`.
- Task fields: `title`, `due?` (date), `remind_at?` (datetime), `starred` (bool), `status` (`open` | `done`).
- Note: no extra fields. Display uses `raw_text`.
- Each item keeps its latest `proposal` and `proposal_error`, even after filing, so auto-filed decisions stay inspectable.

## Capture

Input box at the top of every screen, or `POST /api/capture {"text": "..."}`.
The item is stored with `stage=inbox`, `shape=note`, `space=inbox`, and the request returns `201 {id}` immediately.

## Classify

After capture, a background call to `classify(text, context)` produces `{shape, space, title, due, remind_at, confidence}`.
Context is: current datetime in `TARTIB_TZ`, and the list of existing spaces so proposals converge on the user's own vocabulary.

- `confidence >= TARTIB_AUTOFILE_CONFIDENCE` (default 0.85): proposal applied, `stage=filed`.
- otherwise: proposal attached, `stage=attention`.
- endpoint unset, unreachable, or invalid output: `stage=attention` with no proposal and `proposal_error` set.
- on startup, any item still in `inbox` is re-queued, so a restart mid-classify loses nothing.

## Needs Attention decisions

- Approve: apply the proposal as stored, or with field overrides supplied in the same request. `stage=filed`.
- Reject: file as a Note in space `inbox`. Nothing is deleted. `stage=filed`.

## Editing

Any filed item's `space`, `shape`, `title`, `due`, `remind_at`, `starred`, and `status` can be changed. `raw_text` cannot.

## Screens

1. Today: open tasks due today in `TARTIB_TZ`, plus starred open tasks, plus open tasks whose `remind_at` has passed. Overdue tasks count as due today.
2. Needs Attention: items in `stage=attention`, oldest first, with approve / edit / reject.
3. All: FTS5 search over `raw_text` and `title`, filter by space and by shape, newest first. Empty query lists everything.
4. Login: one password field. Shown when the session cookie is missing or invalid.

## Out of scope

Projects, tags, pomodoro, push notifications, an "ask" feature, a second AI adapter, offline capture queue, multi-user.
