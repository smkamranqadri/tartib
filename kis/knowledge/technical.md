# Technical

How Tartib is built. Proven by the Phase 1 to 4 scaffold on 2026-09-17.

## Layout

```text
backend/tartib/     FastAPI app. config, db, deps, auth, captures, items, spaces, queries, ask, briefs, classify, codex, runner, reminders, push, vapid, store, clock, reclassify, main
backend/tartib/migrations/   numbered .sql, applied at startup, tracked in schema_version
backend/tests/      pytest + TestClient; the AI runs as a real subprocess pointed at fake_codex.py (fake_claude.py for the fallback)
frontend/src/       React + Vite + TS. App.tsx, Capture.tsx, api.ts, push.ts, types.ts, format.ts, useLoad.ts, theme.tsx, screens/ (Home, Inbox, Waiting, Recent, Spaces, Space, SpaceDetail, Settings, ItemPage, Login), components/ (one per pattern, listed under Frontend shell)
frontend/public/    manifest.webmanifest, sw.js (app shell + push; hand-bumped SW_VERSION), icons
Dockerfile          multi-stage: node builds dist; python:3.12-slim + node runtime + @openai/codex + @anthropic-ai/claude-code runs uvicorn
docker-compose.yml  one service, volume tartib-data at /data, ~/.codex mounted at /root/.codex, mem_limit 512m
```

## Serving

One container. Uvicorn, one worker, started with `--factory tartib.main:create_app`.
FastAPI serves `/api/*`; anything else returns a file from the static dir if it exists, otherwise `index.html` (SPA fallback). Unknown `/api/*` paths 404.
In dev, Vite proxies `/api` to port 8000.

## Storage

SQLite, WAL, stdlib `sqlite3`, one connection per request opened in a threadpool. No ORM.
`captures(id, raw_text, source, created_at, status, error, answer_json, classified_at)` is the stored input, one row per capture.
`items` are classifier output: `capture_id`, own `raw_text` excerpt, nullable `space`, task fields, `stage` (attention | filed), `proposal_json`, `proposal_error`, `classified_at`. A CHECK forbids `filed` with a null space. `updated_at` (migration 0003) is internal, set by AFTER INSERT / AFTER UPDATE triggers with millisecond UTC timestamps; the update trigger only fires when the statement did not set `updated_at` itself, so it never recurses.
`briefs(space PK, fingerprint, text, item_ids JSON, created_at)` caches one AI brief per space. Fingerprint = item count and newest item id, so only adding or removing an item regenerates it; the refresh icon forces it.
`spaces(name PK, position, created_at)` (migration 0004) is the list of spaces; `spaces.seed_spaces` fills it from `TARTIB_SPACES` once when empty; `store.list_spaces(conn)` is what the classifier, validation, summary, and reconcile read. Migration 0004 also dropped the item text immutability trigger and made the FTS update trigger fire on `raw_text` too.
At startup, after migrations, `store.reconcile_spaces` moves items whose space is no longer in the `spaces` table to attention with no space. Migration 0002 (2026-09-17) created captures, backfilled one per item, rebuilt items, mapped `space='inbox'` to null + attention, dropped stage=inbox placeholders (their captures stay pending).
`subscriptions(id, endpoint UNIQUE, p256dh, auth, created_at, last_seen_at)` and `app_state(key PK, value)` arrived with migration 0005, which also added `items.reminded_at` (UTC ISO, null = not sent) and wrote off every reminder already due, so the first tick after that deploy is silent. 0005 also narrowed `items_touch_update` to skip writes that change `reminded_at`: a fired reminder is not a human touch and must not reset the stale clock. The one write that clears `reminded_at` (`store.update_fields`, when `remind_at` actually changes) sets `updated_at` itself.
`items_fts` is an FTS5 external-content table over `raw_text` and `title`, synced by triggers.
A BEFORE UPDATE trigger aborts any write to a capture's `raw_text`; the matching trigger on items was dropped in migration 0004, so a filed item's text is editable.
All timestamps stored as UTC ISO 8601 with `Z`; `due` is `YYYY-MM-DD`.

## Auth

`POST /api/login` compares in constant time, sets an HTTP-only SameSite=Lax cookie signed with `itsdangerous`, 30 days.
`secure` flag only when the request scheme is https. Every `/api/*` route except login and health accepts that cookie or `Authorization: Bearer <TARTIB_PASSWORD>`.
`TARTIB_SECRET` is optional; when unset it is derived from the password, so changing the password logs everyone out.

## Classification runtime

`codex.py` is the one AI transport: `run_json(prompt, schema, cfg)` runs the primary CLI and, on any `CodexError`, the fallback if `TARTIB_AI_FALLBACK_COMMAND` is set (dialect by executable name: `claude` -> `claude --print --no-session-persistence --output-format json --json-schema <schema> --tools "" --max-turns 1 [--model M] <prompt>`, reply read from the envelope's `structured_output`; the `CLAUDECODE` env var is stripped so a parent Claude Code session cannot block it). Codex runs `codex exec --ephemeral --skip-git-repo-check --ignore-user-config --sandbox read-only --output-schema <tmp> --output-last-message <tmp> [--model M] <prompt>` with stdin closed (Codex blocks reading stdin otherwise), in a temp working dir so no AGENTS.md leaks in. Timeout kills the process.
`classify.py` builds the filing prompt (user-authored, verbatim, plus a `text` excerpt bullet), validates `{"proposals": [...]}`, and normalizes: questions carry nothing, unknown spaces become null and cap confidence at 0.6, notes drop task fields, naive reminder times are converted from `TARTIB_TZ` to UTC.
`runner.py` queues capture ids. Per capture: classify, insert one item per non-question proposal (excerpt as raw_text, filed or attention by space + threshold), answer the first question proposal via `ask.answer_question` and store it on the capture, mark done. Any failure: one null-space note in attention, capture status error.
`ask.py`: `answer_from_rows(question, rows, settings)` is the Codex step; `answer_question` (POST /api/ask and the runner) retrieves up to 20 items by FTS5 OR-query over the question's content words (stopwords dropped, prefix on words of 4+ chars), falls back to the 20 most recent in the space, sends them to Codex with the user-authored answer prompt (includes current datetime, task status in headers) and a `{answer, item_ids}` schema, then filters cited ids to the retrieved set. Read-only; about 7 to 10s per question.
Tests point `TARTIB_AI_COMMAND` at `tests/fake_codex.py`, driven by `FAKE_CODEX_*` env vars, so the subprocess path is exercised for real.
`runner.py` owns an `asyncio.Queue`; capture enqueues via `call_soon_threadsafe`; one consumer task processes items; startup enqueues every `stage='inbox'` row. Errors are written to `proposal_error` and never retried automatically.
`store.py` is the single write path for filing, shared by the runner, approve, reject, and PATCH.

## Reminders

`reminders.Reminders` is one 60s task started in the lifespan beside the runner's consumer, and only when both VAPID keys are set and `push.check_key` accepts the private one; a bad key logs an error and leaves the loop off rather than consuming reminders nobody could receive. `tick(now)` takes the clock as an argument, so tests drive it.
Due = `stage='filed' AND status='open' AND reminded_at IS NULL AND remind_at <= now AND remind_at > now - 6h`. Anything older than that 6h grace is marked sent without pushing, so a container down overnight does not replay the night. `reminded_at` is set once per item even when every push fails, guarded on the `remind_at` the tick read so a reminder moved mid-push is not swallowed.
One digest per local day at the first tick past `TARTIB_SUMMARY_TIME`, skipped when both counts are zero but still recording the date in `app_state.digest_date`; a first start after that time writes the day off. Payload is `{title, url}`; `url` is always `/today`.
The payload is `{title, url, tag}`; `tag` is `item-<id>` per reminder and `digest` for the digest, so one notification replaces only itself.
`push.py` is the transport and the subscriptions table's owner: `broadcast` pushes to every row and deletes any endpoint answering 404 or 410 at once. Any other failure increments `subscriptions.failures` (migration 0006) and the row is dropped after `MAX_FAILURES` (8) in a row, since a push service is allowed a bad minute but not a permanent one; a delivery or a re-subscribe resets the count to 0. `pywebpush` signs with the private key, which never reaches a response, a log line, or an error body. `python -m tartib.vapid` prints a fresh base64url key pair for `.env`.

## Config (env)

`TARTIB_PASSWORD` (required), `TARTIB_SECRET`, `TARTIB_TZ` (default UTC), `TARTIB_DB_PATH` (default /data/tartib.db), `TARTIB_SPACES` (optional; seeds the spaces table once when it is empty, ignored after that), `TARTIB_STATIC_DIR`, `TARTIB_AI_COMMAND` (default `codex`, `off` disables), `TARTIB_AI_MODEL`, `TARTIB_AI_TIMEOUT` (default 120), `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL`, `CLAUDE_CODE_OAUTH_TOKEN` (passed through to the fallback CLI in Docker), `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85), `TARTIB_VAPID_PUBLIC`, `TARTIB_VAPID_PRIVATE`, `TARTIB_VAPID_EMAIL` (default `mailto:tartib@localhost`), `TARTIB_SUMMARY_TIME` (default `08:00`, read in `TARTIB_TZ`, validated at load). `CODEX_HOME` is passed through to the subprocess.

## API

```text
POST   /api/login {password}     POST /api/logout     GET /api/health (public)
POST   /api/capture {text} -> 201 {id}   (a capture id)
GET    /api/captures/{id} -> capture, its items, and the answer if it was a question
GET    /api/today -> {date, items, recent (newest 3 captures), active_space}
GET    /api/attention -> {items, stale, stale_days}   stale = open filed tasks with updated_at older than 14 days
GET    /api/recent?limit=50&before=<id> -> {captures, next_before}   keyset paging
GET    /api/items?q=&space=&shape=&status=&limit=&before=     GET /api/items/{id}
PATCH  /api/items/{id}   any editable field, including `text` (the item's own text)
DELETE /api/items/{id}   removes the item; its capture stays
POST   /api/items/{id}/approve [overrides]      POST /api/items/{id}/reject
POST   /api/ask {question, space?} -> {answer, item_ids, items, matched}
GET    /api/spaces      POST /api/spaces {name}      names ^[a-z0-9][a-z0-9-]{0,23}$
PATCH  /api/spaces/{name} {name}   rename, cascading to items and briefs
DELETE /api/spaces/{name}          409 unless the space is empty
GET    /api/spaces/summary -> {spaces:[{name, open, notes, overdue, total, last_activity}], unfiled}
GET    /api/spaces/{space}/brief[?refresh=true] -> {space, text, item_ids, items, updated_at, fresh}
       briefs.py; feeds open tasks + 15 newest notes, cap 30, fixed question;
       404 unknown space, 503 AI off, 502 Codex failure; empty space -> "Nothing here yet." with no call
GET    /api/config -> {tz, spaces, ai, fallback, autofile_confidence, vapid_public}   read-only
POST   /api/subscriptions {endpoint, keys:{p256dh, auth}} -> 201 {id}   upserts on endpoint
DELETE /api/subscriptions {endpoint} -> {ok, removed}
GET    /api/subscriptions -> {enabled, count}
```

## Frontend shell

Routes: `/` Home (dashboard), `/inbox`, `/inbox/attention` (every waiting item), `/inbox/recent` (paged captures), `/spaces`, `/spaces/:name`, `/settings`, `/items/:id`. Redirects: `/attention`, `/attention/all`, `/recent`, `/today`, `/search`, `/all`. Pill nav Home · Inbox · Spaces · Settings; the Inbox pill stays active across all three inbox routes.
`push.ts` owns the browser side: permission is only ever requested from the Settings button, a subscription is re-minted when it was made with a superseded VAPID key (and the dead row deleted, since that push fails 403 and nothing prunes it), turning off unsubscribes the browser before the server, and opening Settings re-registers an existing subscription so the card cannot read "on" over a row the server dropped. `sw.js` shows the notification and, on a tap, writes the destination into the shell cache and messages the open tab; the app acts on whichever arrives first, when it next wakes. That routing works on desktop and not on iOS, where the app opens but stays where it was. `sw.js` carries a hand-bumped `SW_VERSION` that Settings displays, because a phone sitting on a stale worker is otherwise invisible.
`App` owns: theme (context in `theme.tsx`, localStorage `tartib-theme`, `data-theme` on `<html>`), the header `Capture` bar (auto-growing textarea up to 6 lines, Enter saves, Shift+Enter newline, mic via Web Speech API when `SpeechRecognition` exists, Add), capture polling and the toast, question answers (navigates to Home to show them), the chat bar (`AskBar`) on `/` and `/inbox` only, and keys `c` / `/`.

One component per pattern, each the only owner of its markup:
- `Row` is the list row primitive (leading, title, meta, right, trailing, actions; long-press reveal). `ItemRow` and `RecentList` compose it; no screen writes row markup.
- `Menu` is the "…" dropdown, taking an items array, closing on selection, Escape, and outside click.
- `Confirm` is the inline "Delete X? Yes / No" line. `NameForm` is the create-and-rename field, owning its own error state.
- `Card` renders section cards and, with `collapsible`/`open`/`onToggle`, the accordions on the space and item pages.
- `PageHead` (optional eyebrow, title, subtitle) and `BackLink` (history-aware, per-page fallback) carry the header convention in SPEC.
- `Status` exports `Loading`, `ErrorLine`, and `Empty`.
- `ApprovalCard` is one waiting item as a decision; `hotkey` binds Enter. `SearchAsk` is the search-or-ask field.
One primary button class (`.primary`), one ghost, one icon button. Space page collapse state lives in localStorage `tartib-space-<name>`.
Tests can steer the fake classifier at runtime through `FAKE_CODEX_REPLY_FILE` (`{"classify": ..., "ask": ...}`); the UI proof injects a fake `SpeechRecognition` to exercise the mic path.

## Maintenance

`python -m tartib.reclassify --all | --attention [--dry-run]` (in Docker: `docker compose exec tartib python -m tartib.reclassify --all`). Deletes the selected captures' items, marks the captures pending, runs the Runner in-process until drained, then carries `starred`/`status` over where a capture still yields one task. Safe with the server up; do not restart the server mid-run. Back up `/data/tartib.db` first (`docker cp tartib-tartib-1:/data/tartib.db …`).

## Verification commands

```sh
cd backend && uv run pytest -q && uv run ruff check .
cd backend && uv run pytest -m eval        # 16 fixtures through real Codex, ~3 min
cd frontend && npm run typecheck && npm run build
docker compose build && docker compose up -d && curl localhost:8000/api/health && docker stats --no-stream
```

UI checks run headless Chrome through playwright-core from the scratchpad (the Claude in Chrome extension was not connected on 2026-09-17).
