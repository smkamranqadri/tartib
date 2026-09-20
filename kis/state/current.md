# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: none in flight. **Slice 24 (presentation) is committed on `main` and not deployed.**
  Plan, every decision and the proof: `kis/intent/slice-24-presentation.md`. Work mode **Phase**.
  A rendered markdown on the item body, thought entries, Ask answers and the space brief,
  flattened the row headline in all five places that compute one, and kept slice 20's search hit
  marked inside the rendered output. B made the item text an editor you tap into rather than a
  mode you enter -- CodeMirror lazily, debounced autosave, a non-modal 409 strip, and a local
  draft so a teardown cannot take your words.
  **Unproved on a device:** whether mono at 14px with markdown suits a long note on a phone.
- **Slice 23 (the UI language) is committed on `main` and not deployed.**
  What it is and why, step by step with its proof: `kis/intent/slice-23-ui.md`; what it changed
  in one line each: `kis/intent/history.md`; the palette and the floors: `kis/knowledge/themes.md`.
  **Not yet seen on a device.** Unproved there: whether mono at 14px suits a long note on a
  phone, and whether `background-attachment: fixed` survives iOS.
- Closed and accepted on the device: **slice 22** (the phone comes first --
  a bottom bar in the nav's shape, capture and ask in a ⊕ sheet, an item read in a sheet,
  one-line headings, 44px targets, the top safe area; fixed furniture on a phone went from 290px
  of 844 to 65px), **slice 21** (four space layouts tried, Panes kept as the space page; Classic,
  Tree, Board and Timeline deleted), **slice 20** (eight items, round three), **slice 19** and
  **slice 18**. Plans: `kis/intent/slice-1{8,9}-*.md`, `kis/intent/slice-2{0,1,2}-*.md`.
- **Nothing since `v1.0` is pushed or deployed.** Slices 18 to 24 are local commits on `main`
  (unpushed). On the next deploy: migrations 0010-0014 run,
  `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come
  out of the CapRover app config, and **`SW_VERSION` in `sw.js` is bumped by hand** -- slices 23
  and 24 both changed the bundle without changing `sw.js`, and a browser re-installs a worker
  only when its bytes differ, so without the bump a phone sits on the old worker and is never
  offered the reload (the rule is in `../knowledge/technical.md`, Frontend shell).
- Next, in no fixed order:
  1. **Backups for the deployed database** (`kis/intent/backlog.md`). Deferred by decision on
     2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so
     everything on that server exists exactly once. This is the one open item whose cost is
     unbounded.
  2. **Look at slices 23 and 24 on a device**, which is the only thing that can settle whether
     mono at 14px suits a long note -- markdown is the best headless answer to it and is now in
     -- and whether `background-attachment: fixed` survives iOS.
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
each one changed. Slice 24 Phase A: 32 browser checks green on channel chrome against the local
container, including stored `<script>` and `<img onerror>` producing no element and no execution,
and a `javascript:` link losing its href -- the app renders markdown from a token stream and
never builds an HTML string, so that holds by construction rather than by a filter. Phase B:
32 checks green on three consecutive runs, covering the caret landing where it was tapped, the
cold page fetching no editor chunk, autosave and its readout, a hard teardown losing nothing,
a two-context conflict resolving both ways without a retry loop, and offline saying so. Proved on the deployed app rather than only in tests: a capture classifies and
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
- **Slices 23 and 24 were proved in headless Chrome only.** Whether mono at 14px is comfortable
  for a long note on a phone is the one decision in slice 23 taken knowingly against
  readability; slice 24's markdown is the strongest answer that can be given to it without a
  device, and it still needs real glass to settle. Slice 24 adds two of its own: whether tapping
  a word is a discoverable way into editing when no button says so, and whether a debounced
  autosave feels safe without a Save button to press.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`, the
desktop Chrome FCM refusal, `pushsubscriptionchange`, the silent worker at session end, voice
capture -- is Knowledge: `../knowledge/technical.md`, "What browsers do to this app".
