# Current

- Local operational detail -- the domain, the backup paths, which devices are subscribed -- lives
  in `kis/state/private.md`, gitignored and never published. This file carries the substance and
  points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
- **Live: `v2.0`**, deployed 2026-09-22 on the CapRover VPS (`x86_64`) as
  `smkamranqadri/tartib:v2.0`. It carries slices 18 to 29 and the fixes from three reviews run
  before release, classifying on the pinned `gpt-5.6-luna` at medium reasoning (confirmed in
  the container over SSH, 2026-09-22). What each slice changed, in a line: `kis/intent/history.md`; the decisions and
  proof: `kis/intent/slice-*.md`.
- **Slice 30 (a split waits for you, Keep as one) is done on branch `sc-superfluid-magnon-e253`**,
  not merged and not deployed; the owner decides when it merges. Plan and proof:
  `kis/intent/slice-30-split-asks.md`. On `main` a different agent's work goes on meanwhile.

## Open

- **On `main` and not deployed, shipping with the next version:** the service-worker cache fix,
  a duplicate of an item deleted mid-classification no longer crashing the capture (`d19dd9d`),
  saving no longer reloading the note, with indented lines keeping their indent (`c91fbf9`), a
  note's icon the size of the checkbox beside it (`1d3383e`), and **checklist boxes tickable** in
  an item's text (`b420ed3`; the first-day checklist report was a missing `- `, not a bug). Each
  was proved in Chrome against local; none has been on a phone. Until the cache fix is out, a new
  version reaches a phone only when Cloudflare's four-hour cache turns over, or after deleting
  and re-adding the app -- which is how `v2.0` got onto the phone. **When it deploys, purge
  `sw.js` from Cloudflare once**, or the copy cached under the old headers lingers.
- **The two captures that were split on the live app (#91, #92) are not repaired**: their 12
  pieces are filed. The repair was blocked twice by the permission check on bulk deletes; the
  owner's call. Keep as one cannot reach them after deploy, since it acts only on waiting pieces.
- **Real data is now accumulating on the deployed database**, and two things are set up to read
  it later. `ai_calls` records what was in each prompt (migration 0017), which cannot be
  backfilled; and `TARTIB_DUPLICATE_PARK` is **off**, so duplicate verdicts are recorded while
  nothing is held back. What it should answer: whether the prompt grows with the database,
  whether the examples are ever real corrections rather than padding, and a real false-positive
  rate for duplicates instead of eight seeded cases.
- **House rules are set on the live app since 2026-09-22** (four rules, written after reading the
  live database). Captures before that day were classified without any, so compare accuracy
  before and after that date when the duplicate verdicts are judged.
- No backups of the deployed database. Deferred by decision on 2026-09-18 and not reopened.

## Next

1. **The next cycle's backlog** (`kis/intent/backlog.md`): first-day feedback on `v2.0` (the
   title, delete in a modal), then links between items, approved 2026-09-22. The fixes above
   ship with it.
2. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
3. **Answer the four questions** under Known gaps, now that `v2.0` is on a device.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **286 passed, 7 deselected** on `main`, and **299 passed, 8 deselected** on the slice 30
  branch and after it merges (the deselected are the evals) and
  **10/10** from `npm run ui`. Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName". The version
  number is a rollback label, and why `v2.0` was not `v1.1` is in `../knowledge/technical.md`,
  Deploy. `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-09-22.2`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

## Proof

Each slice keeps its proof in its plan file and its commits.

**Checked from outside on 2026-09-22, against the live domain:** `/api/health` answers
`{"ok":true,"ai":true}`, the service worker is `2026-09-22.2`, and the content security policy is
served -- which is v2.0 backend code, so the new image is running and not only the new bundle.
**Reported by the owner the same day:** the phone runs `2026-09-22.2`, and push subscribes on the
phone and in desktop Safari. **Re-checked 2026-09-22:** `http://` answers 302 to `https://`, and
the login cookie is `HttpOnly; Secure; SameSite=lax`.

Before release, three reviews -- code, security, and SPEC against the build -- found two things
that must not ship (the retry probe deleted thought logs; model-written markdown could make the
browser fetch a remote URL) and five real bugs. All seven are fixed, each with a test or a
browser reproduction. The whole eval suite passed in one run on the pinned model.

## Known gaps

Offline behaviour that is designed rather than missing -- counts lagging, and text editing
needing one moment online first -- is product truth: `../intent/SPEC.md`, Offline.

- **`v2.0` is on a device, and four questions it can now answer are still open:**
  1. whether mono at 14px suits a long note -- the one decision in slice 23 taken knowingly
     against readability;
  2. whether `background-attachment: fixed` survives iOS;
  3. whether tapping a word is a discoverable way into editing when no button says so. The
     first-day report that the title "can't be edited" bears on this, though it is about the
     title, which tap-to-edit does not cover, rather than the body;
  4. whether a debounced autosave feels safe without a Save button to press.
- The committed UI suite (`npm run ui`, 10 checks) guards slices 22 to 25, 27 and 29. It cannot
  judge how anything reads, and slices 26 and 28 are outside it for a stated reason.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`,
Chromium browsers that cannot reach Google's push service, `pushsubscriptionchange`, the silent
worker at session end, voice capture -- is Knowledge: `../knowledge/technical.md`, "What browsers
do to this app".
