# Tartib (ترتیب)

A personal capture system. You type anything into one box. It is stored once, verbatim, as a capture. A background AI call turns it into one or more items and files them into your own spaces. Confident proposals are filed automatically; the rest wait for you in **Needs Attention**. A capture that is a question is answered from your notes instead of filed.

Your text is never rewritten. Classification only proposes fields around it.

Single user, one password, one container, MIT licensed. Tartib is deliberately small.

![Home at 1280px](docs/screenshots/home-wide.png)

Four screens:

- **Home** — what is due today, overdue, starred, reminded, or worked on in a session today; what needs a decision; what you captured last.
- **Inbox** — the classifier's proposals, to approve or reject, plus tasks that have gone stale.
- **Spaces** — where things live. A brief per space, search across everything, or end with `?` to ask.
- **Settings** — how this copy is set up: theme, classifier, reminders, spaces.

<p>
  <img src="docs/screenshots/inbox-phone.png" width="240" alt="Inbox on a phone, dark theme">
  <img src="docs/screenshots/space-phone.png" width="240" alt="A space and its brief">
  <img src="docs/screenshots/settings-phone.png" width="240" alt="Settings">
</p>

## Run it

Needs Docker and a [Codex CLI](https://github.com/openai/codex) login on the host. Fits in 512MB; it uses about 42MiB at rest.

```sh
codex login                 # once, on the host; compose mounts ~/.codex into the container
cp .env.example .env        # set TARTIB_PASSWORD at least
docker compose up -d
open http://localhost:8000
```

No Codex? Set `TARTIB_AI_COMMAND=off` and every capture goes to Needs Attention for you to file by hand.

**Fallback.** With `TARTIB_AI_FALLBACK_COMMAND=claude`, any Codex failure (usage limit, outage, timeout) is retried once through the Claude Code CLI with the same prompt and schema. Both CLIs are in the image. On the host the Claude login is used as is; inside Docker set `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`.

**Spaces** are managed on the Spaces screen and live in the database. `TARTIB_SPACES` only seeds the table once, when it is empty, and is ignored afterwards.

### Security

One password, one user. Every `/api` route accepts that password as a bearer token as well as the session cookie, which is what makes shortcuts and scripts easy and also means the password is the only thing between anyone and everything. There is no second factor. Put it behind HTTPS and treat the password as the whole security model.

Guessing is slowed by a global backoff: four failures are free, then each further attempt gets `429` with a `Retry-After`, in a window that doubles from 30 seconds and stops at five minutes. It hangs off the password comparison rather than the login route, so it covers the bearer header too — otherwise guesses would simply move to a route nobody was watching. It is global rather than per-IP because behind a proxy the client address only arrives in a header, and one password is one account. While blocked, a correct password is refused as well: checking it would say which guess was right. A browser already holding a valid session cookie is never affected, so nobody can log you out by hammering the door.

The session cookie is marked `Secure` only when the app sees an HTTPS request. Behind a reverse proxy that needs uvicorn to trust `X-Forwarded-Proto`; the image runs with `--proxy-headers --forwarded-allow-ips "*"`, which is safe precisely because nothing reaches the port except the proxy in front of it.

### Environment

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TARTIB_PASSWORD` | yes | | The one password. |
| `TARTIB_SECRET` | no | derived from password | Cookie signing key. Set it to keep sessions across password changes. |
| `TARTIB_TZ` | no | `UTC` | IANA zone that defines "today" and resolves "tomorrow" in captures. |
| `TARTIB_SPACES` | no | | Comma-separated. Seeds the spaces table once, when empty. Ignored after that. |
| `TARTIB_DB_PATH` | no | `/data/tartib.db` | SQLite file. |
| `TARTIB_STATIC_DIR` | no | set by the image | Where the built frontend is served from. |
| `TARTIB_AI_COMMAND` | no | `codex` | Command that runs the Codex CLI. `off` disables classification. |
| `TARTIB_AI_MODEL` | no | | Passed as `codex --model`. Unset uses Codex's default. |
| `TARTIB_AI_TIMEOUT` | no | `120` | Seconds allowed per classification. |
| `TARTIB_AI_FALLBACK_COMMAND` | no | | `claude` to use the Claude Code CLI when Codex fails. Same prompts and schemas. |
| `TARTIB_AI_FALLBACK_MODEL` | no | | Passed as `claude --model`. |
| `CLAUDE_CODE_OAUTH_TOKEN` | no | | Read by the Claude CLI itself. Needed for the fallback inside Docker. |
| `TARTIB_AUTOFILE_CONFIDENCE` | no | `0.85` | Proposals at or above this are filed without asking. |
| `TARTIB_VAPID_PUBLIC` | no | | Web Push key pair. Without both keys the reminder loop does not run. |
| `TARTIB_VAPID_PRIVATE` | no | | Generate with `cd backend && uv run python -m tartib.vapid`. |
| `TARTIB_VAPID_EMAIL` | no | `mailto:tartib@localhost` | A contact the push service can reach. |
| `TARTIB_SUMMARY_TIME` | no | `08:00` | One daily digest, at the first tick past this time in `TARTIB_TZ`. |
| `TARTIB_SESSION_MINUTES` | no | `25` | Every pomodoro is this long. No per-session choice. |

## Deploy it

There is a `captain-definition`, so a [CapRover](https://caprover.com) instance can build and deploy this from the repository directly. That is not the route used here: the image carries a Node runtime and two AI CLIs, and building it on a small VPS is the part that falls over. It is built on a workstation and pushed instead.

```sh
./deploy.sh v1.0        # buildx for linux/amd64, push to Docker Hub
```

Then in CapRover, the app's Deployment tab, "Deploy via ImageName". Tags are immutable versions and there is no `latest`: CapRover deploys by image name, and a tag whose contents changed underneath it can redeploy to the same string and serve either image with nothing to tell them apart. A version per deploy also makes a rollback a choice from a list instead of a rebuild.

Set `TARTIB_IMAGE` for your own Docker Hub namespace, and `TARTIB_PLATFORM` if your server is not amd64. The app needs two persistent directories: `/data` for the database, and `/root/.codex` if you want classification, which means getting a Codex login onto the server.

## Capture from anywhere

Every `/api` route accepts the password as a bearer token, so shortcuts and scripts need no login flow.

```sh
curl -X POST https://tartib.example/api/capture \
  -H "Authorization: Bearer $TARTIB_PASSWORD" \
  -H "Content-Type: application/json" \
  -d '{"text": "call the dentist tomorrow"}'
```

On iOS, an Apple Shortcut with "Get Contents of URL" (POST, JSON body, that header) plus a Share Sheet trigger gives you capture from any app.

## Install it, and capture with no signal

It is a PWA: add it to your home screen and it opens as an app, offline included. The shell is precached at install, so the first launch without a network still opens.

A capture is written to a local queue before it is sent, so the box clears at once and nothing depends on the network. One that cannot go out shows as **waiting to send** and goes when the network or the app comes back, oldest first. Each carries a `client_id`, and `POST /api/capture` answers `200` with the capture it already has if it has seen that id, so a retry is never a second capture.

Reading still needs the network. Tartib shows you nothing offline beyond what you have just typed.

A new version is offered as a line with a Reload rather than swapped in underneath you. Settings shows which service worker is actually installed, which is the only way to tell what a phone is running.

## Reminders and sessions

Web Push, for three things and nothing else: a reminder you set on a task, one daily digest at `TARTIB_SUMMARY_TIME`, and a pomodoro session ending. Turn it on in Settings; permission is only ever asked from that button. Push needs HTTPS, so it will not work from a phone over `http://`.

A session is 25 minutes by default, started on a task or on nothing, and asks **Done · Not finished · Abandoned** when it ends. Today counts them. There is no history screen, no streak, and no chart, on purpose.

Reminders need the container running. A laptop with the lid shut sends nothing.

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

A space's **brief** is the same machinery with a fixed question. It is cached until an item is added or removed, or a session in that space finishes.

## API

```text
POST   /api/login                {password}      sets the session cookie
POST   /api/logout
GET    /api/health                               public
POST   /api/capture              {text, client_id?}  -> 201 {id}, or 200 for a client_id already seen
GET    /api/captures/{id}                        capture, its items, answer if any
GET    /api/today                                items, today's sessions, recent captures
GET    /api/attention                            waiting items, plus 14-day stale tasks
GET    /api/recent?limit=&before=                captures, keyset paging
GET    /api/items?q=&space=&shape=&status=&limit=&before=
GET    /api/items/{id}
PATCH  /api/items/{id}           any of text, shape, space, title, due, remind_at, starred, status
DELETE /api/items/{id}                           removes the item; its capture stays
POST   /api/items/{id}/approve   optional overrides, same fields
POST   /api/items/{id}/reject
POST   /api/ask                  {question, space?} -> {answer, item_ids, items}   read-only
GET    /api/spaces               POST /api/spaces {name}
PATCH  /api/spaces/{name}        {name}          rename, cascading to items and briefs
DELETE /api/spaces/{name}                        409 unless the space is empty
GET    /api/spaces/summary
GET    /api/spaces/{space}/brief[?refresh=true]
GET    /api/config                               read-only view of how this copy is set up
POST   /api/subscriptions        {endpoint, keys}    DELETE and GET on the same path
POST   /api/sessions             {item_id?}      -> 201; 409 while one is running
GET    /api/sessions/current
POST   /api/sessions/{id}/stop   POST /api/sessions/{id}/outcome {outcome}
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
uv run pytest -m eval      # 16 real captures through the real Codex CLI, about 3 minutes
uv run ruff check .

# frontend (proxies /api to :8000)
cd frontend
npm install
npm run dev
npm run typecheck && npm run build
```

Backend is FastAPI on stdlib `sqlite3` with FTS5 and numbered SQL migrations, no ORM. Tests drive a fake Codex script as a real subprocess, so `codex` itself is never needed for the default suite. Frontend is React + Vite + TypeScript with no UI library. One container serves both.

## How this was built

`kis/` is the project's memory, and it is checked in on purpose: `knowledge/` is what is true, `intent/` is what was planned and why, `state/` is where things stand. `kis/knowledge/rules.md` holds the hard constraints, and every exception to them was argued for in writing before it was allowed. Step-by-step proof for each slice lives in the commit messages.

If you want to know why something is the way it is, that is where the answer is.

## Not planned

Projects, tags, multi-user, offline reading, a chat history for ask. Push and pomodoro were out of scope until they were argued in, under carve-outs recorded in `kis/knowledge/rules.md`; the bar for a fourth is higher than the third. The Claude CLI is a fallback for the same prompts, not a second classifier with its own behaviour.

## License

MIT. See [LICENSE](LICENSE), and [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request.
