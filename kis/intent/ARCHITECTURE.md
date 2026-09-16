# Tartib ARCHITECTURE

Decided 2026-09-17, not yet built. Durable parts move to `kis/knowledge/` once the scaffold proves them.

## Layout

```text
backend/    FastAPI app, uv-managed, Python 3.12
  tartib/
    main.py        app factory, static mount, startup requeue
    db.py          sqlite3 connection (WAL), numbered SQL migrations in migrations/
    auth.py        login/logout, cookie + bearer dependency
    items.py       capture, list/search, patch, approve, reject
    classify.py    classify(text, context) -> Proposal, OpenAI-compatible HTTP via httpx
    runner.py      background classification: asyncio queue, startup requeue
  tests/           pytest + httpx TestClient, fake AI endpoint via respx
frontend/   React + Vite + TypeScript PWA
  src/
    api.ts         fetch wrapper, 401 -> login
    screens/       Today, Attention, All, Login
    Capture.tsx    the input box, mounted on every screen
Dockerfile         multi-stage: build frontend, copy dist into backend image
docker-compose.yml one service, one volume for /data
```

## Serving

One container. FastAPI serves `frontend/dist` as static files at `/`, API under `/api`. Uvicorn, one worker.
In dev, Vite dev server proxies `/api` to uvicorn.

## Storage

SQLite at `/data/tartib.db`, WAL mode, one connection per request via stdlib `sqlite3` run in a threadpool. No ORM.
Migrations are numbered `.sql` files applied at startup, tracked in a `schema_version` table.

Tables:
- `items(id, raw_text, space, shape, stage, created_at, title, due, remind_at, starred, status, proposal_json, proposal_error, classified_at)`
- `items_fts` FTS5 external-content table over `raw_text, title`, kept in sync by triggers.
- `schema_version(version)`

## Auth

`POST /api/login {password}` compares against `TARTIB_PASSWORD` in constant time and sets an HTTP-only, SameSite=Lax signed cookie.
Every `/api/*` route except `login` and `health` requires either that cookie or `Authorization: Bearer <TARTIB_PASSWORD>`.

## Classification runtime

`POST /api/capture` inserts the row, then puts the id on an in-process `asyncio.Queue`.
One consumer task drains the queue, calls `classify`, and writes the result. Failures are written as `proposal_error`, never retried automatically.
On startup the consumer first enqueues every item with `stage='inbox'`.
`classify` sends a chat completion with `response_format: json_object`, a fixed system prompt, and validates the reply with a Pydantic model.

## Configuration (env)

```text
TARTIB_PASSWORD                required
TARTIB_SECRET                  cookie signing key, required
TARTIB_TZ                      IANA zone, default UTC
TARTIB_DB_PATH                 default /data/tartib.db
TARTIB_AI_BASE_URL             OpenAI-compatible base URL; unset disables AI
TARTIB_AI_API_KEY
TARTIB_AI_MODEL
TARTIB_AUTOFILE_CONFIDENCE     default 0.85
```

## API

```text
POST   /api/login                {password}
POST   /api/logout
GET    /api/health
POST   /api/capture              {text} -> 201 {id}
GET    /api/today
GET    /api/attention
GET    /api/items?q=&space=&shape=&limit=&before=
GET    /api/spaces               distinct spaces, for filters and classify context
PATCH  /api/items/{id}           any editable field
POST   /api/items/{id}/approve   optional field overrides
POST   /api/items/{id}/reject
```

## Tooling and proof

Backend: `uv run pytest`, `uv run ruff check`. Frontend: `npm run typecheck`, `npm run build`.
Whole stack: `docker compose up`, then `curl` a capture and `docker stats` under 512MB.

## Phases

1. Scaffold: layout, DB + migrations, auth, capture, health, Vite shell with login + capture box, Dockerfile, compose.
2. Classify: adapter, runner, startup requeue, approve / reject / patch.
3. Screens: Today, Needs Attention, All with FTS and filters.
4. Ship: PWA manifest + app-shell service worker, README, LICENSE (MIT), memory check.
