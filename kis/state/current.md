# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: none in flight. Closed and accepted on the device: **slice 22** (the phone comes first --
  a bottom bar in the nav's shape, capture and ask in a ⊕ sheet, an item read in a sheet,
  one-line headings, 44px targets, the top safe area; fixed furniture on a phone went from 290px
  of 844 to 65px), **slice 21** (four space layouts tried, Panes kept as the space page; Classic,
  Tree, Board and Timeline deleted), **slice 20** (eight items, round three), **slice 19** and
  **slice 18**. Plans: `kis/intent/slice-1{8,9}-*.md`, `kis/intent/slice-2{0,1,2}-*.md`.
- **Nothing since `v1.0` is pushed or deployed.** Slices 18 to 22 are local commits on `main`
  (60 ahead of `origin/main`). On the next deploy: migrations 0010-0014 run, and
  `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come
  out of the CapRover app config.
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

- Verify: `cd backend && uv run pytest -q` and `uv run pytest -m eval` (two tests: 22 classify
  fixtures and 3 tell-it-why cases, ~30s, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
  As of 2026-09-20 pytest is **193 passed, 2 deselected** (the two deselected are the evals).
  Any red is real.
- Deploy: `./deploy.sh v1.1`, then CapRover's Deployment tab, "Deploy via ImageName".
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.

## Proof

Each slice keeps its proof in its plan file and its commits; `../intent/history.md` says what
each one changed. Proved on the deployed app rather than only in tests: a capture classifies and
files itself, the session cookie carries `Secure` behind the proxy, a session ending pushes and
the phone buzzes with a desktop tab open on the same countdown (the migration 0008 case), and
`http://` redirects.

## Known gaps

- The phone layout (slice 22) was proved in headless Chrome with the insets emulated, not on a
  real device: a phone has no header at all now, and the page itself reserves the top inset.
  Unchecked on glass until it is on the phone -- which needs `v1.1`, or the local container over
  the LAN.
- **The app shows no data offline.** The shell opens and a capture still queues, but the screens
  are empty, because the service worker never caches an `/api/` response. Deliberate -- slice 15
  scoped offline *read* out -- and an approved backlog item now, with offline editing.
- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox also shows.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`, the
desktop Chrome FCM refusal, `pushsubscriptionchange`, the silent worker at session end, voice
capture -- is Knowledge: `../knowledge/technical.md`, "What browsers do to this app".
