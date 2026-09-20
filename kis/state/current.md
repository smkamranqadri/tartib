# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: none in flight.
- **Slices 23 (the UI language), 24 (presentation) and 25 (offline) are committed on `main`,
  not deployed, and have never been seen on a device.** What each changed, in a line:
  `kis/intent/history.md`; the decisions and the proof: `kis/intent/slice-2{3,4,5}-*.md`.
  What being unseen leaves unsettled is under Known gaps.
- **Slices 18 to 22 are closed and accepted on a device.** Plans: `kis/intent/slice-1{8,9}-*.md`,
  `kis/intent/slice-2{0,1,2}-*.md`; what each one changed, in a line: `kis/intent/history.md`.
- **Nothing since `v1.0` is pushed or deployed.** Slices 18 to 25 are local commits on `main`
  (unpushed). On the next deploy: migrations 0010-0014 run,
  `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come
  out of the CapRover app config, and **`SW_VERSION` in `sw.js` is bumped by hand** -- slices 23
  and 24 changed the bundle without changing `sw.js`; slice 25 changed `sw.js` itself and bumped
  it to `2026-09-21.1`, so that debt is paid unless another bundle-only change lands first. The
  rule and its reason are in `../knowledge/technical.md`, Frontend shell.
- Next, in no fixed order:
  1. **Backups for the deployed database** (`kis/intent/backlog.md`). Deferred by decision on
     2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so
     everything on that server exists exactly once. This is the one open item whose cost is
     unbounded.
  2. **Look at slices 23, 24 and 25 on a device** -- the only thing that can settle what Known gaps
     lists against them. Needs `v1.1`, or the local container over the LAN.
  3. Then slice 14 (AI contract) and the rest of `kis/intent/backlog.md`. Both halves of
     backlog 13 are now accounted for: themes closed, presentation is slice 24.

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
  As of 2026-09-21 pytest is **193 passed, 2 deselected** (the two deselected are the evals).
  Any red is real.
- Deploy: `./deploy.sh v1.1`, then CapRover's Deployment tab, "Deploy via ImageName".
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.

## Proof

Each slice keeps its proof in its plan file and its commits; `../intent/history.md` says what
each one changed. Slices 24 and 25 are the fullest, if an example is wanted.

Proved on the deployed app rather than only in tests: a capture classifies and files itself, the
session cookie carries `Secure` behind the proxy, a session ending pushes and the phone buzzes
with a desktop tab open on the same countdown (the migration 0008 case), and `http://` redirects.

## Known gaps

Offline behaviour that is designed rather than missing -- counts lagging, and text editing
needing one moment online first -- is product truth: `../intent/SPEC.md`, Offline.

- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox also shows.
- **Slices 23, 24 and 25 were proved in headless Chrome only.** Four things wait on glass:
  whether mono at 14px suits a long note -- the one decision in slice 23 taken knowingly
  against readability, and slice 24's markdown is the best answer to it that can be given
  without a device; whether `background-attachment: fixed` survives iOS; whether tapping a word
  is a discoverable way into editing when no button says so; and whether a debounced autosave
  feels safe without a Save button to press.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`, the
desktop Chrome FCM refusal, `pushsubscriptionchange`, the silent worker at session end, voice
capture -- is Knowledge: `../knowledge/technical.md`, "What browsers do to this app".
