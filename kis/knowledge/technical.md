# Technical

How Tartib is built. Proven by the Phase 1 to 4 scaffold on 2026-09-17.

## Layout

```text
backend/tartib/     FastAPI app. config, db, auth, items, queries, store, classify, runner, main
backend/tartib/migrations/   numbered .sql, applied at startup, tracked in schema_version
backend/tests/      pytest + TestClient; AI endpoint mocked with respx
frontend/src/       React + Vite + TS. api.ts, screens/, components/, format.ts, useLoad.ts
frontend/public/    manifest.webmanifest, sw.js, icons
Dockerfile          multi-stage: node builds dist, python:3.12-slim runs uvicorn, dist copied to /app/static
docker-compose.yml  one service, volume tartib-data at /data, mem_limit 512m
```

## Serving

One container. Uvicorn, one worker, started with `--factory tartib.main:create_app`.
FastAPI serves `/api/*`; anything else returns a file from the static dir if it exists, otherwise `index.html` (SPA fallback). Unknown `/api/*` paths 404.
In dev, Vite proxies `/api` to port 8000.

## Storage

SQLite, WAL, stdlib `sqlite3`, one connection per request opened in a threadpool. No ORM.
`items` holds everything: shared fields, task fields, `stage`, `proposal_json`, `proposal_error`, `classified_at`.
`items_fts` is an FTS5 external-content table over `raw_text` and `title`, synced by triggers.
A BEFORE UPDATE trigger aborts any write to `raw_text`.
All timestamps stored as UTC ISO 8601 with `Z`; `due` is `YYYY-MM-DD`.

## Auth

`POST /api/login` compares in constant time, sets an HTTP-only SameSite=Lax cookie signed with `itsdangerous`, 30 days.
`secure` flag only when the request scheme is https. Every `/api/*` route except login and health accepts that cookie or `Authorization: Bearer <TARTIB_PASSWORD>`.
`TARTIB_SECRET` is optional; when unset it is derived from the password, so changing the password logs everyone out.

## Classification runtime

`classify(text, context)` in `classify.py` posts a chat completion with `response_format: json_object` and `temperature: 0`, validates with a Pydantic `Proposal`, drops task fields for notes, and converts naive reminder times from `TARTIB_TZ` to UTC.
`runner.py` owns an `asyncio.Queue`; capture enqueues via `call_soon_threadsafe`; one consumer task processes items; startup enqueues every `stage='inbox'` row. Errors are written to `proposal_error` and never retried automatically.
`store.py` is the single write path for filing, shared by the runner, approve, reject, and PATCH.

## Config (env)

`TARTIB_PASSWORD` (required), `TARTIB_SECRET`, `TARTIB_TZ` (default UTC), `TARTIB_DB_PATH` (default /data/tartib.db), `TARTIB_STATIC_DIR`, `TARTIB_AI_BASE_URL`, `TARTIB_AI_API_KEY`, `TARTIB_AI_MODEL`, `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85). Unset base URL disables AI.

## API

```text
POST   /api/login {password}        POST /api/logout        GET /api/health (public)
POST   /api/capture {text} -> 201 {id}
GET    /api/today                    GET /api/attention      GET /api/spaces
GET    /api/items?q=&space=&shape=&limit=&before=     GET /api/items/{id}
PATCH  /api/items/{id}               POST /api/items/{id}/approve [overrides]   POST /api/items/{id}/reject
```

## Verification commands

```sh
cd backend && uv run pytest -q && uv run ruff check .
cd frontend && npm run typecheck && npm run build
docker compose build && docker compose up -d && curl localhost:8000/api/health && docker stats --no-stream
```

UI checks run headless Chrome through playwright-core from the scratchpad (the Claude in Chrome extension was not connected on 2026-09-17).
