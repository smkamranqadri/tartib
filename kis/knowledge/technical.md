# Technical

How Tartib is built. Proven by the Phase 1 to 4 scaffold on 2026-09-17.

## Layout

```text
backend/tartib/     FastAPI app. config, db, auth, captures, items, queries, ask, store, codex, classify, runner, main
backend/tartib/migrations/   numbered .sql, applied at startup, tracked in schema_version
backend/tests/      pytest + TestClient; AI endpoint mocked with respx
frontend/src/       React + Vite + TS. api.ts, screens/ (Today, Attention, All, ItemPage, Login), components/ (Card, ItemRow, ItemEditor), format.ts, useLoad.ts
frontend/public/    manifest.webmanifest, sw.js, icons
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
At startup, after migrations, `store.reconcile_spaces` moves items whose space is not in `TARTIB_SPACES` to attention with no space. Migration 0002 (2026-09-17) created captures, backfilled one per item, rebuilt items, mapped `space='inbox'` to null + attention, dropped stage=inbox placeholders (their captures stay pending).
`items_fts` is an FTS5 external-content table over `raw_text` and `title`, synced by triggers.
A BEFORE UPDATE trigger aborts any write to `raw_text`.
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

## Config (env)

`TARTIB_PASSWORD` (required), `TARTIB_SECRET`, `TARTIB_TZ` (default UTC), `TARTIB_DB_PATH` (default /data/tartib.db), `TARTIB_SPACES` (required, comma-separated), `TARTIB_STATIC_DIR`, `TARTIB_AI_COMMAND` (default `codex`, `off` disables), `TARTIB_AI_MODEL`, `TARTIB_AI_TIMEOUT` (default 120), `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL`, `CLAUDE_CODE_OAUTH_TOKEN` (passed through to the fallback CLI in Docker), `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85). `CODEX_HOME` is passed through to the subprocess.

## API

```text
POST   /api/login {password}        POST /api/logout        GET /api/health (public)
POST   /api/capture {text} -> 201 {id}   (capture id)     GET /api/captures/{id}
GET    /api/today                    GET /api/attention      GET /api/spaces
GET    /api/items?q=&space=&shape=&status=&limit=&before=     GET /api/items/{id}
POST   /api/ask {question, space?} -> {answer, item_ids, items, matched}
GET    /api/spaces/summary -> {spaces:[{name, open, notes, overdue, total, last_activity}], unfiled}
GET    /api/spaces/{space}/brief[?refresh=true] -> {space, text, item_ids, items, updated_at, fresh}   (briefs.py; feeds open tasks + 15 newest notes, cap 30, fixed question; 404 unknown space, 503 AI off, 502 Codex failure; empty space -> "Nothing here yet." with no call)
GET    /api/today also returns active_space; recent = newest 10 captures
GET    /api/attention -> {items, stale, stale_days}   stale = open filed tasks with updated_at older than 14 days
GET    /api/config -> {tz, spaces, ai, fallback, autofile_confidence}   read-only
GET/POST /api/spaces, PATCH /api/spaces/{name} {name} (rename cascades to items and briefs), DELETE /api/spaces/{name} (409 unless empty)   names ^[a-z0-9][a-z0-9-]{0,23}$
PATCH  /api/items/{id} also accepts text (the item's own text)     DELETE /api/items/{id} (capture stays)
GET    /api/recent?limit=50&before=<id> -> {captures, next_before}   keyset paging; Today recent = 3
PATCH  /api/items/{id}               POST /api/items/{id}/approve [overrides]   POST /api/items/{id}/reject
```

## Frontend shell

Routes: `/` Home (dashboard; DOM order Today, Needs attention, Recent = phone order; grid areas put Needs attention right on desktop), `/attention` Inbox (3 `ApprovalCard`s, Stale, Recent), `/attention/all` (every waiting item as cards), `/spaces` (cards, New space in the title row, grouped search; `?space=` redirects), `/spaces/:name` (`Space` page: back, filter + manage in the title row, scoped search, `SpaceDetail`), `/recent` (paged), `/settings`, `/items/:id` (editable text, File it / Proposal accordions closed once filed, original capture shown when different, delete), `/today` -> `/`. Pill nav with inline SVG icons (`components/Icons.tsx`).
`App` owns: theme (context in `theme.tsx`, localStorage `tartib-theme`, `data-theme` on `<html>`), the header `Capture` bar (auto-growing textarea up to 6 lines, Enter saves, Shift+Enter newline, mic via Web Speech API when `SpeechRecognition` exists, Add), capture polling and the toast, question answers (navigates to Home to show them), the chat bar (`AskBar`) on `/` and `/attention` only, and keys `c` / `/`.
Components: `ApprovalCard` (one waiting item as a decision; `hotkey` binds Enter), `PageHead` (eyebrow, h1, subtitle), `Card` (icon + uppercase label + right aside), `ItemRow` (meta line, due at right, hover/long-press actions), `SearchAsk` (search-or-ask field), `SpaceDetail` (brief, tasks, notes; collapse state in localStorage `tartib-space-<name>`).
Layout: app column max 1240px; dashboard grid 1.5fr/1fr above 900px; single column below. Tokens: teal accent, green-tinted near-black dark theme, matching light theme.
Tests can steer the fake classifier at runtime through `FAKE_CODEX_REPLY_FILE` (`{"classify": ..., "ask": ...}`); the UI proof injects a fake `SpeechRecognition` to exercise the mic path.

## Maintenance

`python -m tartib.reclassify --all | --attention [--dry-run]` (in Docker: `docker compose exec tartib python -m tartib.reclassify --all`). Deletes the selected captures' items, marks the captures pending, runs the Runner in-process until drained, then carries `starred`/`status` over where a capture still yields one task. Safe with the server up; do not restart the server mid-run. Back up `/data/tartib.db` first (`docker cp tartib-tartib-1:/data/tartib.db …`).

## Verification commands

```sh
cd backend && uv run pytest -q && uv run ruff check .
cd backend && uv run pytest -m eval        # 15 fixtures through real Codex, ~3 min
cd frontend && npm run typecheck && npm run build
docker compose build && docker compose up -d && curl localhost:8000/api/health && docker stats --no-stream
```

UI checks run headless Chrome through playwright-core from the scratchpad (the Claude in Chrome extension was not connected on 2026-09-17).
