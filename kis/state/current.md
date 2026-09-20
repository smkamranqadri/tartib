# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: none in flight. **Slice 26 (retrieval) is done and committed on `main`**, not deployed.
  The plan, the three things it did not foresee, and the proof: `kis/intent/slice-26-retrieval.md`.
- **Slices 23 (the UI language), 24 (presentation), 25 (offline) and 26 (retrieval) are
  committed on `main`, not deployed, and have never been seen on a device.** What each changed,
  in a line: `kis/intent/history.md`; the decisions and the proof: `kis/intent/slice-2{3,4,5,6}-*.md`.
  What being unseen leaves unsettled is under Known gaps.
- **Slices 18 to 22 are closed and accepted on a device.** Plans: `kis/intent/slice-1{8,9}-*.md`,
  `kis/intent/slice-2{0,1,2}-*.md`; what each one changed, in a line: `kis/intent/history.md`.
- **Nothing since `v1.0` is pushed or deployed.** Slices 18 to 26 are local commits on `main`
  (unpushed). On the next deploy: migrations 0010-0014 run,
  `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come
  out of the CapRover app config, and **`SW_VERSION` in `sw.js` is bumped by hand**. It is at
  `2026-09-21.2`: slice 26 changed the bundle without touching `sw.js`, which is exactly the
  case the rule exists for, so it was bumped with the slice rather than left for the deploy.
  Nothing outstanding unless another bundle-only change lands before `v1.1`. The rule and its
  reason are in `../knowledge/technical.md`, Frontend shell.
- Next, in no fixed order:
  1. **Backups for the deployed database** (`kis/intent/backlog.md`). Deferred by decision on
     2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so
     everything on that server exists exactly once. This is the one open item whose cost is
     unbounded.
  2. **`v1.1`, and look at slices 23 to 26 on a device.** Now the next thing: slice 26 was the
     work `v1.1` was waiting for. This is the only thing that can settle what Known gaps lists
     against 23, 24 and 25.
  3. Then slice 14 (AI contract), which is now prompt work only -- slice 26 took its retrieval
     half out and closed two backlog entries doing it. Then the rest of `kis/intent/backlog.md`.

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
  As of 2026-09-21 pytest is **206 passed, 3 deselected** (the three deselected are the evals;
  slice 26 added the third). `cd frontend && npm run ui` is the committed UI suite -- 8 checks
  re-running slices 22 to 25 against the local container, needs `TARTIB_PASSWORD` in the
  environment and real Chrome.
  Any red is real.
- Deploy: `./deploy.sh v1.1`, then CapRover's Deployment tab, "Deploy via ImageName".
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.

## Proof

Each slice keeps its proof in its plan file and its commits; `../intent/history.md` says what
each one changed. Slices 24 and 25 are the fullest, if an example is wanted.

Slice 26's headline proof, because it is the one number that could have gone the other way:
showing the classifier what already exists took six deliberately ambiguous captures from
**0/6 to 6/6** on space, with the existing 22 fixtures unchanged. Measured on this build against
the real Codex CLI, not carried over from an earlier one.

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
