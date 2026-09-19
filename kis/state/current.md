# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: **slice 19, small items round two** -- approved 2026-09-19. Steps 1 to 4 done; step 5 next. Plan:
  `kis/intent/slice-19-small-items-2.md`. Mode: Standard.
- Slice 18, small fixes, closed 2026-09-19, not deployed:
  `kis/intent/slice-18-small-fixes.md`. When `v1.1` ships, `TARTIB_AI_FALLBACK_COMMAND`,
  `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come out of the CapRover app config.
- Next, in no fixed order:
  1. **Backups for the deployed database** (`kis/intent/backlog.md`). Deferred by decision on
     2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so
     everything on that server exists exactly once. This is the one open item whose cost is
     unbounded.
  2. Slice 13 (presentation), slice 14 (AI contract) and the rest of `kis/intent/backlog.md`,
     with the theme palettes as data in `kis/intent/themes.md`.

## The deployment

- Running: `smkamranqadri/tartib:v1.0` on the CapRover VPS (`x86_64`), with the Codex login made
  on the server and classifying from there. The next deploy is `v1.1`. How the deploy is
  configured and why is Knowledge: `kis/knowledge/technical.md`, Deploy.
- Local development runs `docker compose up -d --build` against http://localhost:8000.

## Open

- **The deployed `v1.0` still carries the Claude fallback**, which hangs for the full 120s
  timeout on that host, so a Codex failure there costs 120s per capture and fails anyway. Removed
  from the code in slice 18 step 1; gone from the server at `v1.1`. Until then, unsetting
  `TARTIB_AI_FALLBACK_COMMAND` in the dashboard makes those failures instant. Why it hung was
  never found and no longer matters.
- No backups of the deployed database. See Next.

## Commands

- Verify: `cd backend && uv run pytest -q` and `uv run pytest -m eval` (22 real-Codex fixtures,
  needs a Codex login); `cd frontend && npm run typecheck && npm run build`. As of 2026-09-19
  pytest is **159 passed** (slice 18 removed the 5 fallback tests and added 1); any red is real.
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

The SHAs above are post-rewrite and current; history is not rewritten again (`technical.md`,
Maintenance).

## Known gaps

- Slice 18's sticky glass nav and safe-area insets were checked on the phone only in the browser
  over the LAN. The installed app's header against the real notch is unchecked until `v1.1`.
- **The app shows no data offline.** The shell opens and a capture still queues, but Today,
  Needs Attention and Recent are all empty, because the service worker never caches an `/api/`
  response. Deliberate -- slice 15 scoped offline *read* out -- and proved in Chrome on
  2026-09-19. Now an approved backlog item, with offline editing, which has no queue at all.
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
- The service worker shows nothing when a session ends with the app on screen. Browsers allow
  that only within a budget for `userVisibleOnly` pushes; if Chrome ever says "This site has been
  updated in the background", make that path a silent notification instead of none.
