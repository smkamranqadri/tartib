# Tartib (ترتیب)

A personal capture system. You type anything into one box. It lands in an inbox. A background AI call proposes how to file it. Confident proposals are filed automatically; the rest wait for you in **Needs Attention**. Three screens, nothing else.

- **Today**: open tasks due today or earlier, starred tasks, and tasks whose reminder time has passed.
- **Needs Attention**: captures the AI was not sure about. Approve, edit, or reject.
- **All**: full-text search over everything, filter by space and shape.

Your text is never rewritten. Classification only proposes fields around it.

## Run it

Needs Docker. Fits in 512MB.

```sh
cp .env.example .env        # set TARTIB_PASSWORD, optionally the AI endpoint
docker compose up -d
open http://localhost:8000
```

Put it behind HTTPS (Caddy, a tunnel, a reverse proxy) before exposing it beyond your LAN. The session cookie is marked secure only when the request arrives over HTTPS.

### Environment

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TARTIB_PASSWORD` | yes | | The one password. |
| `TARTIB_SECRET` | no | derived from password | Cookie signing key. Set it to keep sessions across password changes. |
| `TARTIB_TZ` | no | `UTC` | IANA zone that defines "today" and resolves "tomorrow" in captures. |
| `TARTIB_AI_BASE_URL` | no | | OpenAI-compatible base URL, e.g. `https://api.openai.com/v1`. Unset disables AI; everything goes to Needs Attention. |
| `TARTIB_AI_API_KEY` | no | | Bearer key for that endpoint. |
| `TARTIB_AI_MODEL` | no | | Model name. |
| `TARTIB_AUTOFILE_CONFIDENCE` | no | `0.85` | Proposals at or above this are filed without asking. |
| `TARTIB_DB_PATH` | no | `/data/tartib.db` | SQLite file. |

Any OpenAI-compatible server works: OpenAI, OpenRouter, Ollama (`http://host.docker.internal:11434/v1`), LM Studio, vLLM.

## Capture from anywhere

Every `/api` route accepts the password as a bearer token, so shortcuts and scripts need no login flow.

```sh
curl -X POST https://tartib.example/api/capture \
  -H "Authorization: Bearer $TARTIB_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{"text": "call the dentist tomorrow"}'
```

On iOS, an Apple Shortcut with "Get Contents of URL" (POST, JSON body, that header) plus a Share Sheet trigger gives you capture from any app. Add the PWA to your home screen for the input box.

## How filing works

1. `POST /api/capture` stores the text and returns immediately.
2. A background task calls the AI with the text, the current time in your zone, and your existing spaces.
3. The AI proposes `{shape, space, title, due, remind_at, confidence}`.
4. Confidence at or above the threshold: applied and filed. Below: parked in Needs Attention with the proposal attached. Endpoint down or unconfigured: parked with the error.
5. Restart mid-classify loses nothing. Anything still in the inbox is re-queued on startup.

**Reject** keeps the text as a plain note in the `inbox` space. Nothing is ever deleted by a decision.

## API

```text
POST   /api/login                {password}      sets the session cookie
POST   /api/logout
GET    /api/health                               public
POST   /api/capture              {text}          -> 201 {id}
GET    /api/today
GET    /api/attention
GET    /api/items?q=&space=&shape=&limit=&before=
GET    /api/items/{id}
GET    /api/spaces
PATCH  /api/items/{id}           any of shape, space, title, due, remind_at, starred, status
POST   /api/items/{id}/approve   optional overrides, same fields
POST   /api/items/{id}/reject
```

Dates: `due` is `YYYY-MM-DD`. `remind_at` and `created_at` are ISO 8601 in UTC.

## Develop

```sh
# backend
cd backend
uv sync
TARTIB_PASSWORD=dev TARTIB_DB_PATH=./dev.db uv run uvicorn --factory tartib.main:create_app --reload
uv run pytest
uv run ruff check .

# frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev
npm run typecheck && npm run build
```

Backend is FastAPI on stdlib `sqlite3` with FTS5 and numbered SQL migrations, no ORM. Frontend is React + Vite + TypeScript with no UI library. One container serves both.

## Not planned

Projects, tags, pomodoro, push notifications, chat with your notes, a second AI provider, multi-user. Tartib is deliberately small.

## License

MIT.
