# Technical

How Tartib is built. Proven by the Phase 1 to 4 scaffold on 2026-09-17.

## Layout

```text
backend/tartib/     FastAPI app. config, db, deps, auth, captures, items, spaces, queries, ask, briefs, classify, codex, runner, reminders, sessions, push, vapid, store, clock, reclassify, main
backend/tartib/migrations/   numbered .sql, applied at startup, tracked in schema_version
backend/tests/      pytest + TestClient; the AI runs as a real subprocess pointed at fake_codex.py
frontend/src/       React + Vite + TS. App.tsx, Capture.tsx, api.ts, push.ts, types.ts, format.ts, useLoad.ts, theme.tsx, screens/ (Home, Inbox, Waiting, Recent, Spaces, Space, SpaceDetail, Settings, ItemPage, Login), components/ (one per pattern, listed under Frontend shell)
frontend/public/    manifest.webmanifest, sw.js (app shell + push; hand-bumped SW_VERSION), icons 180/192/512
Dockerfile          multi-stage: node builds dist; python:3.12-slim + node runtime + @openai/codex runs uvicorn
docker-compose.yml  one service, volume tartib-data at /data, ~/.codex mounted at /root/.codex, mem_limit 512m
```

## Serving

One container. Uvicorn, one worker, started with `--factory tartib.main:create_app`.
FastAPI serves `/api/*`; anything else returns a file from the static dir if it exists, otherwise `index.html` (SPA fallback). Unknown `/api/*` paths 404.
In dev, Vite proxies `/api` to port 8000.

## Storage

SQLite, WAL, stdlib `sqlite3`, one connection per request opened in a threadpool. No ORM.
`captures(id, raw_text, source, created_at, status, error, answer_json, classified_at, client_id)` is the stored input, one row per capture. `client_id` (migration 0009) is minted by the browser before its first send, so a capture queued offline and sent twice is recognised rather than duplicated: `POST /api/capture` looks it up and answers 200 with the existing id instead of 201 with a new one, and the unique index settles the race when two sends both find nothing. It is nullable and unique only among rows that have one -- SQLite allows repeated NULLs in a unique index -- because every capture from curl, the Shortcut, or before 0009 has none. A repeat is never re-enqueued; the first attempt did that, and startup re-queues anything still pending.
`items` are classifier output: `capture_id`, own `raw_text` excerpt, nullable `space`, task fields, `stage` (attention | filed), `proposal_json`, `proposal_error`, `classified_at`. A CHECK forbids `filed` with a null space. `updated_at` (migration 0003) is internal, set by AFTER INSERT / AFTER UPDATE triggers with millisecond UTC timestamps; the update trigger fires only when the statement neither set `updated_at` itself (so it never recurses) nor changed `reminded_at` (narrowed by 0005, below).
`briefs(space PK, fingerprint, text, item_ids JSON, created_at)` caches one AI brief per space. Fingerprint = item count, newest item id, and today's session count for the space, so adding or removing an item or finishing a session in it regenerates the brief; the refresh icon forces it. The prompt gains a line with that count when it is not zero. Fingerprints are only checked when a brief is opened, so a session costs a Codex call only the next time that brief is looked at.
`spaces(name PK, position, created_at)` (migration 0004) is the list of spaces; `spaces.seed_spaces` fills it from `TARTIB_SPACES` once when empty; `store.list_spaces(conn)` is what the classifier, validation, summary, and reconcile read. Migration 0004 also dropped the item text immutability trigger and made the FTS update trigger fire on `raw_text` too.
At startup, after migrations, `store.reconcile_spaces` moves items whose space is no longer in the `spaces` table to attention with no space. Migration 0002 (2026-09-17) created captures, backfilled one per item, rebuilt items, mapped `space='inbox'` to null + attention, dropped stage=inbox placeholders (their captures stay pending).
`subscriptions(id, endpoint UNIQUE, p256dh, auth, created_at, last_seen_at, failures)` (the last column from 0006) and `app_state(key PK, value)` arrived with migration 0005, which also added `items.reminded_at` (UTC ISO, null = not sent) and wrote off every reminder already due, so the first tick after that deploy is silent. 0005 also narrowed `items_touch_update` to skip writes that change `reminded_at`: a fired reminder is not a human touch and must not reset the stale clock. The one write that clears `reminded_at` (`store.update_fields`, when `remind_at` actually changes) sets `updated_at` itself.
`items_fts` is an FTS5 external-content table over `raw_text` and `title`, synced by triggers.
A BEFORE UPDATE trigger aborts any write to a capture's `raw_text`; the matching trigger on items was dropped in migration 0004, so a filed item's text is editable.
All timestamps stored as UTC ISO 8601 with `Z`; `due` is `YYYY-MM-DD`.

## Auth

`POST /api/login` compares in constant time, sets an HTTP-only SameSite=Lax cookie signed with `itsdangerous`, 30 days.
`secure` flag only when the request scheme is https. Every `/api/*` route except login and health accepts that cookie or `Authorization: Bearer <TARTIB_PASSWORD>`.
`TARTIB_SECRET` is optional; when unset it is derived from the password, so changing the password logs everyone out.
`auth.check_password` is the one place a password is compared, and the backoff lives there rather than on the login route: every `/api` route also takes the password as a bearer token, so watching `/api/login` alone would just move guessing to `/api/today`. The count is global, not per-IP -- behind a proxy the address only arrives in a header, and one password is one account. Four failures are free; from the fifth each attempt answers 429 with `Retry-After`, in a window doubling from 30s and capped at 5 minutes, and a success clears it. Counters live in `app_state` (`login_failures`, `login_blocked_until`), so a crash loop is not a free reset. While blocked the password is not even compared: doing so would be an oracle saying which guess was right, and the price is that your own login waits too. `require_auth` tries the cookie first so a signed-in browser never consults the counter and cannot be locked out by someone else's guessing.
The image runs uvicorn with `--proxy-headers --forwarded-allow-ips "*"`. `--proxy-headers` alone trusts `X-Forwarded-Proto` only from `127.0.0.1`, and behind a reverse proxy the peer is the container network, so the app saw `http` and set the session cookie without `Secure` on an HTTPS site. `"*"` is safe in this shape only: nothing reaches the port except the proxy.

## Classification runtime

`codex.py` is the one AI transport: `run_json(prompt, schema, cfg)` runs the Codex CLI and raises `CodexError` on any failure; there is no fallback. Codex runs `codex exec --ephemeral --skip-git-repo-check --ignore-user-config --sandbox read-only --output-schema <tmp> --output-last-message <tmp> [--model M] <prompt>` with stdin closed (Codex blocks reading stdin otherwise), in a temp working dir so no AGENTS.md leaks in. Timeout kills the process.
`classify.py` builds the filing prompt (user-authored, verbatim, plus a `text` excerpt bullet), validates `{"proposals": [...]}`, and normalizes: questions carry nothing, unknown spaces become null and cap confidence at 0.6, notes drop task fields, naive reminder times are converted from `TARTIB_TZ` to UTC.
`runner.py` queues capture ids. Per capture: classify, insert one item per non-question proposal (excerpt as raw_text, filed or attention by space + threshold), answer the first question proposal via `ask.answer_question` and store it on the capture, mark done. Any failure: one null-space note in attention, capture status error.
`ask.py`: `answer_from_rows(question, rows, settings)` is the Codex step; `answer_question` (POST /api/ask and the runner) retrieves up to 20 items by FTS5 OR-query over the question's content words (stopwords dropped, prefix on words of 4+ chars), falls back to the 20 most recent in the space, sends them to Codex with the user-authored answer prompt (includes current datetime, task status in headers) and a `{answer, item_ids}` schema, then filters cited ids to the retrieved set. Read-only; about 7 to 10s per question.
Tests point `TARTIB_AI_COMMAND` at `tests/fake_codex.py`, driven by `FAKE_CODEX_*` env vars, so the subprocess path is exercised for real.
`runner.py` owns an `asyncio.Queue`; capture enqueues via `call_soon_threadsafe`; one consumer task processes captures; startup enqueues every `status='pending'` capture. Errors are written to `proposal_error`. Failed captures are retried (slice 19): a probe every `RETRY_INTERVAL` (15 min) and a pass after every successful classification reset them to pending, at most `MAX_RETRIES` (3) times, counted in `captures.attempts` (migration 0010). Only while the capture's one item is still exactly what the fallback wrote -- note, no space, title, due or reminder, unstarred, open, text unchanged, `proposal_json` null -- so anything a person has started on is never discarded. `AI not configured` is never retried, and the probe does not run with AI off. The reclassify CLI builds its Runner with `retry=False`.
`POST /api/items {shape, space, text, due?}` files an item by hand (slice 20): a capture with `source='web'`, `status='done'` and `direct=1` (migration 0011; a column because `source` is a CHECK constraint SQLite cannot widen without a table rebuild), and one filed item with no proposal. The runner only reads `pending`, retry only `error`, and `reclassify` skips `direct=1`, so the classifier never sees it. A proposal files itself by `store.should_file(space, confidence, threshold, policies)` (slice 20): no space never files; otherwise `spaces.policy` (migration 0012) decides -- `ask` never, `file` always, `auto` by `TARTIB_AUTOFILE_CONFIDENCE`. `GET /api/spaces` returns `policies` beside `spaces`; `PUT /api/spaces/{name}/policy`. A rename carries the policy with the row. `store.py` is the single write path for filing, shared by the runner, approve, reject, and PATCH. `PATCH /api/items/{id}` takes an optional `expected_updated_at` (slice 19): when present and not equal to the stored `updated_at`, it returns 409 and writes nothing. The item page's text edit and Edit form send it and offer Reload or Overwrite on a 409; row and accordion toggles (star, done) never send it. The check reads then writes on one connection, so two requests landing in the same instant could both pass -- accepted for one user.

## Reminders

`reminders.Reminders` is one 60s task started in the lifespan beside the runner's consumer, and only when both VAPID keys are set and `push.check_key` accepts the private one; a bad key logs an error and leaves the loop off rather than consuming reminders nobody could receive. `tick(now)` takes the clock as an argument, so tests drive it.
Due = `stage='filed' AND status='open' AND reminded_at IS NULL AND remind_at <= now AND remind_at > now - 6h`. Anything older than that 6h grace is marked sent without pushing, so a container down overnight does not replay the night. `reminded_at` is set once per item even when every push fails, guarded on the `remind_at` the tick read so a reminder moved mid-push is not swallowed.
One digest per local day at the first tick past `TARTIB_SUMMARY_TIME`, skipped when both counts are zero but still recording the date in `app_state.digest_date`; a first start after that time writes the day off. Payload is `{title, url}`; `url` is always `/today`.
The payload is `{title, url, tag}`; `tag` is `item-<id>` per reminder and `digest` for the digest, so one notification replaces only itself.
Tapping a reminder on iOS opens Tartib but does not route to the notification's URL. Three approaches were tried and each was confirmed installed on the phone before being ruled out: `WindowClient.navigate()` after `focus()` (does nothing to a frozen client), `postMessage` with a reply and a `navigate()` fallback (a home-screen app is frozen while the worker runs and cannot answer in time), and the worker writing the URL into the shell cache for the app to pick up on waking, read on mount, `visibilitychange`, `focus`, `pageshow` and a short burst of retries. The third is what ships: it is correct, proved on desktop, and costs nothing. Whether iOS dispatches `notificationclick` to the worker at all was never established, and is the first thing to check if this is picked up again.
`push.py` is the transport and the subscriptions table's owner: `broadcast` pushes to every row and deletes any endpoint answering 404 or 410 at once. Any other failure increments `subscriptions.failures` (migration 0006) and the row is dropped after `MAX_FAILURES` (8) in a row, since a push service is allowed a bad minute but not a permanent one; a delivery or a re-subscribe resets the count to 0. A tick charges at most one failure per endpoint however many notifications it sends, or a batch of reminders during one outage would spend every strike and delete a live subscription.
Neither column is evidence that a push arrived. `mark_delivered` only clears a non-zero count and
never touches `last_seen_at`, so a good delivery leaves both looking exactly as they did before;
`failures = 0` equally describes "nothing failed" and "nothing was ever sent". What proves a send
is the caller's own claim (`items.reminded_at`, `sessions.notified_at`) together with the absence
of a strike: `pywebpush` raises `WebPushException` on any non-2xx, and `broadcast` turns that into
a counted failure and a log line.
A failure to subscribe in the browser is not a server problem: `pushManager.subscribe()` talks to
the browser's own push service and the app only POSTs the resulting endpoint afterwards, so
Chrome's "Registration failed - push service error" means it could not register with FCM. The
same VAPID key working on another browser is enough to rule the key out.
`/api/config` hands out `vapid_public` only when a push could actually be delivered: keys that fail `push.check_key` leave the loop off, and the UI must not offer to switch on something that can never fire. `pywebpush` signs with the private key, which never reaches a response, a log line, or an error body. `python -m tartib.vapid` prints a fresh base64url key pair for `.env`.

## Sessions

`sessions(id, item_id NULL, started_at, ends_at, ended_at, outcome, created_at)` (migration 0007) is the pomodoro log. `item_id` is nullable and `ON DELETE SET NULL`: a session is about a task or about nothing, and deleting the task must not erase the time spent. `outcome` is `done | unfinished | abandoned`, null until answered; `done` ticks the task through `store.update_fields`. Only today's counts read this table -- rule 4 forbids the history screen.
`sessions.Sessions` schedules one asyncio timer per running session for that session's own `ends_at`, not on the reminder loop's 60s tick, and re-arms everything unfinished at startup. Announcing a session is its own claim, held on `notified_at` (migration 0008) and separate from closing the row: a page whose countdown reached zero asks the server immediately, and while the two shared a column that read took the notification with it, on the device that was not the one needing to be told. A session stopped by hand or already announced never pushes; nothing is pushed if the end is more than `PUSH_GRACE` (5 min) past. One session runs at a time, but one still owed an outcome does not block the next, and it stops being offered after `OUTCOME_WINDOW` (12 h).
`TARTIB_SESSION_MINUTES` (default 25) is the only length; there is no per-session choice.

## Config (env)

`TARTIB_PASSWORD` (required), `TARTIB_SECRET`, `TARTIB_TZ` (default UTC), `TARTIB_DB_PATH` (default /data/tartib.db), `TARTIB_SPACES` (optional; seeds the spaces table once when it is empty, ignored after that), `TARTIB_STATIC_DIR`, `TARTIB_AI_COMMAND` (default `codex`, `off` disables), `TARTIB_AI_MODEL`, `TARTIB_AI_TIMEOUT` (default 120), `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85), `TARTIB_VAPID_PUBLIC`, `TARTIB_VAPID_PRIVATE`, `TARTIB_VAPID_EMAIL` (default `mailto:tartib@localhost`), `TARTIB_SUMMARY_TIME` (default `08:00`, read in `TARTIB_TZ`, validated at load), `TARTIB_SESSION_MINUTES` (default 25, at least 1). `CODEX_HOME` is passed through to the subprocess.

## API

```text
POST   /api/login {password}     POST /api/logout     GET /api/health (public)
POST   /api/capture {text} -> 201 {id}   (a capture id)
GET    /api/captures/{id} -> capture, its items, and the answer if it was a question
GET    /api/today -> {date, items, recent (newest 3 captures), active_space, sessions {total, by_item}}
       items are open filed tasks due today or earlier, starred, with a passed reminder, or
       worked on in a session today
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
GET    /api/config -> {tz, spaces, ai, autofile_confidence, vapid_public}   read-only
POST   /api/subscriptions {endpoint, keys:{p256dh, auth}} -> 201 {id}   upserts on endpoint
DELETE /api/subscriptions {endpoint} -> {ok, removed}
GET    /api/subscriptions -> {enabled, count}
POST   /api/sessions {item_id?} -> 201 the session; 409 while one is running
GET    /api/sessions/current -> {state: running | awaiting | null, session, item}
POST   /api/sessions/{id}/stop          stop early; the row is kept and still owed an outcome
POST   /api/sessions/{id}/outcome {outcome}
```

## Frontend shell

`session.tsx` holds the running pomodoro: it renders a countdown against the server's `ends_at`, re-asks whenever the app comes back, and is what `SessionBar` and the start controls read. `SessionBar` sits under the capture bar on every screen and turns into the Done / Not finished / Abandoned question in place; there is no modal, here or anywhere.
Routes: `/` Home (dashboard), `/inbox`, `/inbox/attention` (every waiting item), `/inbox/recent` (paged captures), `/spaces`, `/spaces/:name`, `/settings`, `/items/:id`. Redirects: `/attention`, `/attention/all`, `/recent`, `/today`, `/search`, `/all`. Pill nav Home · Inbox · Spaces · Settings; the Inbox pill stays active across all three inbox routes.
`sw.js` precaches at install rather than waiting for a navigation to fill the cache: it fetches
`index.html`, reads the hashed `/assets/` URLs out of it with a regex, and caches those with the
icons and the manifest. Caching the HTML alone was not enough -- it only names the assets, so the
first offline launch after an install rendered a blank page with a title. Every put is settled
individually, so one missing file cannot fail the install and leave the old worker in place.
It does not call `skipWaiting()` on install. A new worker waits, `update.ts` notices it and the
app offers one line -- "A new version is ready" with Reload -- which posts `tartib:skip-waiting`
and reloads once `controllerchange` fires. Only a handover the user asked for reloads: that event
also fires the first time a worker claims a page that had none. `sw.js` also handles
`pushsubscriptionchange`, re-subscribing with the key `push.ts` leaves at `/__vapid-key` in the
shell cache and re-registering against `/api/subscriptions` with `credentials: "include"`; Safari
does not fire that event, so on the phone it is insurance rather than a fix.
`manifest.webmanifest` has an `id` and a `start_url` of `/` (it was `/today`, a redirect, so every
launch paid one). `index.html` carries a `theme-color` per colour scheme so the first paint is
right before any script runs, and `App` overwrites both with the active theme's background when
the chosen theme is not the system's. `background_color` is a single dark value and the app has
two themes, so one of them gets a mismatched splash; a manifest cannot know which.
`offline.ts` is the capture queue and the only path a capture takes: `enqueue` writes it to an
IndexedDB store keyed by `client_id`, then `flush` sends what is queued oldest first and stops at
the first one that does not go, so a later capture cannot overtake an earlier one. Ordering lives
in the sort in `list()`, not the store -- `getAll()` returns key order. A 4xx that is not 401 or
429 leaves the queue and surfaces in the toast, since it can never succeed and would wedge
everything behind it; 401 and 5xx stay queued. `watchForReconnect` flushes on `online` and on the
same wake points `push.ts` watches, not Background Sync, which Safari does not have. Both capture
lists render pending rows even when their server load failed, which is exactly when there are any.
`useLoad` owns every screen's load error and says "You're offline." rather than the browser's
"Failed to fetch".
`push.ts` owns the browser side: permission is only ever requested from the Settings button, a subscription is re-minted when it was made with a superseded VAPID key (and the dead row deleted, since that push fails 403 and nothing prunes it), turning off unsubscribes the browser before the server, and opening Settings re-registers an existing subscription so the card cannot read "on" over a row the server dropped. `sw.js` shows the notification and, on a tap, writes the destination into the shell cache and messages the open tab; the app acts on whichever arrives first, when it next wakes. That routing works on desktop and not on iOS, where the app opens but stays where it was. `sw.js` carries a hand-bumped `SW_VERSION` that Settings displays, because a phone sitting on a stale worker is otherwise invisible. Bump it on every release that changes the app, not only when `sw.js` changes: a browser re-installs a worker only when its bytes differ, so a bundle-only release leaves the old worker active and never offers the reload.
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

## Deploy

`captain-definition` (schemaVersion 2, pointing at the Dockerfile) exists so anyone else can
one-click this onto CapRover, but it is not the route used: the image is built on the
workstation by `deploy.sh` and pushed to Docker Hub, and CapRover deploys it by image name. The
VPS has the disk but building a Node-plus-two-CLIs image there is what falls over. This machine
is arm64 and the server is not, so `deploy.sh` runs `docker buildx build --platform linux/amd64`
under QEMU; `TARTIB_IMAGE` and `TARTIB_PLATFORM` override the defaults. The script refuses to
overwrite a tag that already exists, because the tags are immutable versions and there is no
`latest` -- CapRover redeploying the same string could otherwise serve either image.

On CapRover the container's HTTP port must be set to 8000, not the default 80, and there is no
host port mapping: mapping one would bypass nginx, and with it TLS and the `X-Forwarded-Proto`
header the `Secure` session cookie depends on. Force HTTPS is on, so `http://` answers 302. The
persistent directories are `/data` (the database) and `/root/.codex` (the Codex login). The
deployed database is separate from the local one and always has been.

The Codex CLI authenticates with a device code, so `codex login` works over SSH on a headless
server with no browser callback and no credential files to carry. On CapRover it is run inside
the container, because the persistent directory is a labelled volume and the host's own
`~/.codex` is a different directory the container never sees. The mount is read-write so the
CLI's token refresh persists.

## Maintenance

`python -m tartib.reclassify --all | --attention [--dry-run]` (in Docker: `docker compose exec tartib python -m tartib.reclassify --all`). Deletes the selected captures' items, marks the captures pending, runs the Runner in-process until drained, then carries `starred`/`status` over where a capture still yields one task. Safe with the server up; do not restart the server mid-run. Back up `/data/tartib.db` first (`docker cp tartib-tartib-1:/data/tartib.db …`).

History is not rewritten. It was rewritten three times on 2026-09-18, all before the first push
(one identity, then the domain and private-network setup scrubbed, then a second email address
removed); the repository has been public since, so any further rewrite would be a force-push
over published history. Scrub by commit going forward, never by rewrite.

## Verification commands

```sh
cd backend && uv run pytest -q && uv run ruff check .
cd backend && uv run pytest -m eval        # 22 fixtures through real Codex, ~30s
cd frontend && npm run typecheck && npm run build
docker compose build && docker compose up -d && curl localhost:8000/api/health && docker stats --no-stream
```

UI checks run headless Chrome through playwright-core from the scratchpad (the Claude in Chrome extension was not connected on 2026-09-17).
