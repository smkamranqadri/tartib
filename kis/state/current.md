# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public,
  working tree clean. `v1.0` is tagged and released.
- Task: none in flight. Slices 12, 15, 16 and 17 are all closed. Tartib runs on its own host,
  behind HTTPS, reachable from the phone, and is in real use -- which is what slices 15 to 17
  existed for. Plans: `kis/intent/slice-1{5,6,7}-*.md`.
- Next, in no fixed order and none of it started:
  1. **Backups for the deployed database** (`kis/intent/backlog.md`). Deferred by decision on
     2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so
     everything on that server exists exactly once. This is the one open item whose cost is
     unbounded.
  2. **The Claude fallback hang**, below.
  3. Slice 13 (presentation) and slice 14 (AI contract), approved in the backlog, unplanned.

## The deployment

- One container on a CapRover VPS (`x86_64`), image `smkamranqadri/tartib:v1.0` from Docker Hub,
  deployed by image name. Tags are immutable versions with no `latest`: the next deploy is
  `v1.1`, and `deploy.sh` refuses to overwrite a tag that exists.
- Container HTTP Port must be 8000, not CapRover's default 80. No host port mapping -- that would
  bypass nginx and with it TLS and `X-Forwarded-Proto`, which is what the `Secure` cookie needs.
- Persistent directories at `/data` and `/root/.codex`. The Codex login was made on the server
  with a device code, and classification works from there.
- Force HTTPS is on; `http://` answers 302.
- The database starts and remains separate from the local one. Local development still runs
  `docker compose up -d --build` against http://localhost:8000.

## Open

- **The Claude fallback does not run on the deployed host.** With Codex broken deliberately the
  fallback is invoked and hangs for the full 120s timeout. Ruled out: the token (present in the
  container), Tartib's invocation (running the CLI there by hand hangs identically), and the
  network (`api.anthropic.com` and `console.anthropic.com` both connect over IPv4). IPv6 is
  unreachable from the container but cannot be the cause -- an unreachable network errors
  instantly. The hang is inside the CLI's own startup there.
  It is still configured on the server as of 2026-09-18, so a Codex failure costs 120s per
  capture and fails anyway; captures queue serially. Unsetting `TARTIB_AI_FALLBACK_COMMAND`
  makes those failures instant, and is a one-field change in the dashboard.
- No backups of the deployed database. See Next.

## Commands

- Verify: `cd backend && uv run pytest -q` (163 passed) and `uv run pytest -m eval` (16
  real-Codex fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Deploy: `./deploy.sh v1.1`, then CapRover's Deployment tab, "Deploy via ImageName".
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.

## Proof

Finished slices keep their step-by-step proof in the commit messages, not here. Slices 11 and 12:
`34ab011`, `fc75770`, `e2e31cc`, `91d7a22`, `970348e`, `7e7f294`. Slice 15: `81ffc81`, `e11dcf1`,
`5423d4d`. Slice 16: `bb1df57`, `90ac360`, `7ec12e1`. Slice 17: `1a2bbcb`, `5031388`, `6d7170c`,
`5c103b2`, `3a966db`, `57837ea`, `5b36d25`, `c315141`.

Proved on the deployed app, not only in tests: a capture classifies and files itself; the session
cookie carries `Secure` behind the proxy; a session ending pushes and the phone buzzes **with a
desktop tab open on the same countdown**, which is the migration 0008 case that had never been
tested on real devices; `http://` redirects.

History was rewritten three times on 2026-09-18, all before publication: once to one identity,
once to scrub the domain and the private-network setup, once to remove the second email address.
Every SHA changed each time and the citations above are the current ones. That budget is spent --
the repository is public, so any further rewrite is a force-push.

Earlier (v0.1): every route driven headlessly at 390px and 1280px with the fake classifier; real
Codex exercised on the host for classification, briefs, and ask.

## Known gaps

- The Claude fallback does not run in the deployed container (above), so a Codex outage parks
  captures in the Inbox, slowly.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox screen also shows.
- `pushsubscriptionchange` is handled since slice 15, but unproved: it needs a push service to
  retire an endpoint, and Safari never fires the event.
- Tapping a reminder on iOS opens Tartib but does not navigate to `/today`. Whether iOS runs the
  worker's `notificationclick` at all was never established; `technical.md` records what was tried.
- One device is subscribed to push. A desktop Chrome fails to subscribe with "Registration failed
  - push service error", which is the browser failing to register with FCM and not a Tartib
  problem: `pushManager.subscribe()` never contacts the server, and iOS accepted the same key.
  Not worth chasing unless wanted -- one switch covers all three pushers, so a desktop
  subscription means two buzzes for every reminder and digest.
- `SW_VERSION` (now `2026-09-18.7`) must be bumped whenever the app changes, not only when
  `sw.js` does: a browser re-installs a worker only when its bytes differ, so a bundle-only
  release would leave the old worker active and offer no reload.
- The service worker shows nothing when a session ends with the app on screen. Browsers allow
  that only within a budget for `userVisibleOnly` pushes; if Chrome ever says "This site has been
  updated in the background", make that path a silent notification instead of none.
