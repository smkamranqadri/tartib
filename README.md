# Tartib (ترتیب)

A personal capture system. You type anything into one box. It is stored once, verbatim, as a capture. A background Codex call turns it into one or more items, filed into your own spaces. Confident proposals are filed automatically; the rest wait for you in **Needs Attention**. A capture that is a question is answered from your notes instead of filed. Three screens, nothing else.

- **Today**: open tasks due today or earlier, starred tasks, tasks whose reminder time has passed, and your three most recent captures.
- **Ask bar**: pinned to the bottom of every screen. A question in, an answer drawn only from your own items out, with links.
- **Needs Attention**: captures the AI was not sure about. Approve, edit, or reject.
- **All**: full-text search over everything, filter by space, shape, and status.
- **Item page**: the full text, the AI's proposal, and inline edit.

Your text is never rewritten. Classification only proposes fields around it.

## Run it

Needs Docker and a [Codex CLI](https://github.com/openai/codex) login on the host. Fits in 512MB.

```sh
codex login                 # once, on the host; compose mounts ~/.codex into the container
cp .env.example .env        # set TARTIB_PASSWORD and TARTIB_SPACES
docker compose up -d
open http://localhost:8000
```

No Codex? Set `TARTIB_AI_COMMAND=off` and every capture goes to Needs Attention for you to file by hand.

**Fallback.** With `TARTIB_AI_FALLBACK_COMMAND=claude`, any Codex failure (usage limit, outage, timeout) is retried once through the Claude Code CLI with the same prompt and schema. Both CLIs are in the image. On the host the Claude login is used as is; inside Docker set `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`.

Put it behind HTTPS (Caddy, a tunnel, a reverse proxy) before exposing it beyond your LAN. The session cookie is marked secure only when the request arrives over HTTPS.

### Environment

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TARTIB_PASSWORD` | yes | | The one password. |
| `TARTIB_SECRET` | no | derived from password | Cookie signing key. Set it to keep sessions across password changes. |
| `TARTIB_TZ` | no | `UTC` | IANA zone that defines "today" and resolves "tomorrow" in captures. |
| `TARTIB_SPACES` | yes | | Comma-separated. The only spaces that exist. |
| `TARTIB_AI_COMMAND` | no | `codex` | Command that runs the Codex CLI. `off` disables classification. |
| `TARTIB_AI_MODEL` | no | | Passed as `codex --model`. Unset uses Codex's default. |
| `TARTIB_AI_TIMEOUT` | no | `120` | Seconds allowed per classification. |
| `TARTIB_AI_FALLBACK_COMMAND` | no | | `claude` to use the Claude Code CLI when Codex fails. Same prompts and schemas. |
| `TARTIB_AI_FALLBACK_MODEL` | no | | Passed as `claude --model`. |
| `CLAUDE_CODE_OAUTH_TOKEN` | no | | Needed for the fallback inside Docker. Get it with `claude setup-token` on the host. |
| `TARTIB_AUTOFILE_CONFIDENCE` | no | `0.85` | Proposals at or above this are filed without asking. |
| `TARTIB_DB_PATH` | no | `/data/tartib.db` | SQLite file. |

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

1. `POST /api/capture` stores the text once as a capture and returns `{id}` immediately.
2. A background task runs `codex exec` (ephemeral, read-only sandbox, JSON output schema) with the text, the current time in your zone, and your configured spaces.
3. Codex returns a list of proposals, one per independent item in the text: `{text, shape, space, title, due, remind_at, confidence}`. "A, B, and C" becomes three items, each with its own verbatim excerpt.
4. Per proposal: `question` is not stored, the runner answers it from your items and keeps the answer on the capture. A space outside your list becomes null. Null space or confidence below the threshold: Needs Attention. Otherwise filed.
5. CLI missing, failing, or timing out: one plain note in Needs Attention with the error. Restart mid-classify loses nothing; pending captures are re-queued on startup.

`GET /api/captures/{id}` returns the capture, its items, and the answer if it was a question. The PWA polls it after every capture.

**Reject** discards the proposal and keeps the item in Needs Attention with no space, for you to file through Edit. **Approve** needs a space. Nothing is ever deleted by a decision; the capture keeps the original text either way.

## How ask works

`POST /api/ask` runs FTS5 over the question's content words (OR, prefix on longer words) and takes the top 20 matches, or the 20 most recent items in the chosen space when nothing matches. Those items go to Codex with a prompt that allows answering only from them and asks for the ids it relied on. The reply is `{answer, item_ids, items}`. It never writes anything. Expect about 7 to 10 seconds per question.

## API

```text
POST   /api/login                {password}      sets the session cookie
POST   /api/logout
GET    /api/health                               public
POST   /api/capture              {text}          -> 201 {id}   (a capture id)
GET    /api/captures/{id}                        capture, its items, answer if any
GET    /api/today
GET    /api/attention
GET    /api/items?q=&space=&shape=&status=&limit=&before=
GET    /api/items/{id}
GET    /api/spaces                               TARTIB_SPACES
POST   /api/ask                  {question, space?} -> {answer, item_ids, items}   read-only
PATCH  /api/items/{id}           any of shape, space, title, due, remind_at, starred, status
POST   /api/items/{id}/approve   optional overrides, same fields
POST   /api/items/{id}/reject
```

Dates: `due` is `YYYY-MM-DD`. `remind_at` and `created_at` are ISO 8601 in UTC.

## Re-run the classifier

After changing spaces or the prompt, rebuild items from their captures:

```sh
docker cp tartib-tartib-1:/data/tartib.db ./tartib-backup.db     # first
docker compose exec tartib python -m tartib.reclassify --all        # or --attention, add --dry-run to preview
```

Done and starred carry over when a capture still produces one task. Manual edits to space, title, or dates do not.

## Develop

```sh
# backend
cd backend
uv sync
TARTIB_PASSWORD=dev TARTIB_DB_PATH=./dev.db uv run uvicorn --factory tartib.main:create_app --reload
uv run pytest              # fast, offline, fake Codex
uv run pytest -m eval      # 15 real captures through the real Codex CLI, about 3 minutes
uv run ruff check .

# frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev
npm run typecheck && npm run build
```

Backend is FastAPI on stdlib `sqlite3` with FTS5 and numbered SQL migrations, no ORM. Tests drive a fake Codex script as a real subprocess, so `codex` itself is never needed for the default suite. Upgrading from a pre-captures database is automatic on startup: every item gets a capture, `inbox` items move to Needs Attention with no space. Frontend is React + Vite + TypeScript with no UI library. One container serves both.

## Not planned

Projects, tags, pomodoro, push notifications, multi-user. Ask is a single question with a single answer; there is no chat history. The Claude CLI is a fallback for the same prompts, not a second classifier with its own behaviour. Tartib is deliberately small.

## License

MIT.
