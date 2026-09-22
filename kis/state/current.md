# Current

- Local operational detail -- the domain, the backup paths, which device is subscribed, how HTTPS
  reached the phone before the move -- lives in `kis/state/private.md`, gitignored and never
  published. This file carries the substance without the specifics and points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  `v1.0` is tagged and released; `main` is ahead of it, unpushed.
- Task: none in flight. **Slice 29 (what the AI costs) is done and committed on `main`**, not
  deployed. `kis/intent/slice-29-ai-usage.md`. No blockers: one real capture classified end to
  end with `--json` on, and the cost arithmetic reconciles to the penny.
- **One capture costs ~15,600 input tokens, and only ~2,400 of that is Tartib's prompt.** The
  rest is the CLI's own instructions, on every call. That, not slice 26-28's prompt growth, is
  what eats the subscription: an eval run is ~810k input tokens.
- The quota readout is **built and dormant** -- `codex exec` emits no `token_count` event, so the
  windows stay unknown and the line does not render. Not a fault to chase.
  `kis/intent/slice-29-ai-usage.md`. Two things in it will bite if missed: `--json` changes
  where error messages come from, and the cost may double-count reasoning tokens -- **no cost
  figure ships until one real call reconciles the arithmetic.**
- **Slice 28 (what the classifier may name) is done and committed on
  `main`**, not deployed. Park-and-name a duplicate, and proposing a space that does not exist.
  `kis/intent/slice-28-what-the-classifier-may-name.md`. `TARTIB_DUPLICATE_PARK` is **off** by
  design: the verdict is recorded now so it can be judged on real captures before it is ever
  allowed to hold one back.
- Small and worth doing before `v1.1`: one consolidated `uv run pytest -m eval`. Every check has
  passed, but across two runs and **on the CLI's default model** -- the evals did not carry the
  pin until 2026-09-22. Re-running the suite now measures what ships.
  Park-and-name a duplicate, and proposing a space that does not exist yet. Phase mode.
  `kis/intent/slice-28-what-the-classifier-may-name.md`. It starts from a correction: the
  retrieval slice 26 shipped is about the database, not about the capture in hand, so
  per-capture retrieval is part of this slice.
- **Slice 27 (the AI contract) is done and committed on `main`**, not deployed. House rules, the classifier asking which space instead of guessing, and corrections
  as examples. The measurement that closed it caught a regression first -- asking had become a
  way to avoid deciding -- and the fix is recorded with it:
  `kis/intent/slice-27-ai-contract.md`. No blockers.
- The digest stale-count gap is **fixed and committed** (2026-09-21): `store.waiting_counts`
  now owns what "waiting" means and the digest counts both halves.
- Decided 2026-09-21: **nothing goes out yet.** `main` stays unpushed and no image is published
  until you are at the phone; `v1.1` is the next thing, and it now carries this fix too.
- **Slice 26 (retrieval) is done and committed on `main`**, not deployed. The plan, the three
  things it did not foresee, and the proof: `kis/intent/slice-26-retrieval.md`.
- **Slices 23 to 29 are committed on `main`, not deployed, and have never been seen on a
  device.** Slice 29 is also **not proven against the real CLI** -- see the blocker. What each changed,
  in a line: `kis/intent/history.md`; the decisions and the proof:
  `kis/intent/slice-2{3,4,5,6,7,8,9}-*.md`.
  What being unseen leaves unsettled is under Known gaps.
- **Slices 18 to 22 are closed and accepted on a device.** Plans: `kis/intent/slice-1{8,9}-*.md`,
  `kis/intent/slice-2{0,1,2}-*.md`; what each one changed, in a line: `kis/intent/history.md`.
- **Nothing since `v1.0` is pushed or deployed.** Slices 18 to 29 are local commits on `main`
  (unpushed). On the next deploy: migrations 0010-0016 run,
  `TARTIB_AI_FALLBACK_COMMAND`, `TARTIB_AI_FALLBACK_MODEL` and `CLAUDE_CODE_OAUTH_TOKEN` come
  out of the CapRover app config, **`TARTIB_AI_MODEL=gpt-5.6-luna` and
  `TARTIB_AI_REASONING=medium` go in** (pinned 2026-09-21; without them the server keeps
  using whatever default the CLI picks, which can move on its own), and **`SW_VERSION` in `sw.js` is bumped by hand**. It is at
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

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. As of 2026-09-22 the numbers to expect are **264 passed, 7 deselected**
  (the seven are the evals) and **10/10** from the UI suite. Any red is real.
- Deploy: `./deploy.sh v1.1`, then CapRover's Deployment tab, "Deploy via ImageName".
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.

## Proof

Each slice keeps its proof in its plan file and its commits; `../intent/history.md` says what
each one changed in a line. Slices 24, 25 and 28 are the fullest, if an example is wanted.

Proved on the deployed app rather than only in tests: a capture classifies and files itself, the
session cookie carries `Secure` behind the proxy, a session ending pushes and the phone buzzes
with a desktop tab open on the same countdown (the migration 0008 case), and `http://` redirects.
**Everything since is proved locally only.**

## Known gaps

Offline behaviour that is designed rather than missing -- counts lagging, and text editing
needing one moment online first -- is product truth: `../intent/SPEC.md`, Offline.

- **Slices 23 to 29 were proved in headless Chrome only.** Since slice 26 the harness is
  committed (`npm run ui`, 10 checks, 10/10), so what it covers will not silently regress -- but
  it cannot judge how anything *reads*. Unseen on a device, by slice: 26 the Note/Task buttons at
  44px and the ask bar's follow-up carry; 27 the house-rules editor and the classifier's question
  as option buttons; 28 the "Looks like #N" line and the dashed `+ space` button; 29 the usage
  readout in Settings. Four things only glass can answer:
  1. whether mono at 14px suits a long note -- the one decision in slice 23 taken knowingly
     against readability, and slice 24's markdown is the best answer to it available without a
     device;
  2. whether `background-attachment: fixed` survives iOS;
  3. whether tapping a word is a discoverable way into editing when no button says so;
  4. whether a debounced autosave feels safe without a Save button to press.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`, the
desktop Chrome FCM refusal, `pushsubscriptionchange`, the silent worker at session end, voice
capture -- is Knowledge: `../knowledge/technical.md`, "What browsers do to this app".
