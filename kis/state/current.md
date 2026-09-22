# Current

- Local operational detail -- the domain, the backup paths, which devices are subscribed -- lives
  in `kis/state/private.md`, gitignored and never published. This file carries the substance and
  points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  In step with `origin/main` since 2026-09-22 (pushed after `v2.1` went live).
- **Live: `v2.1`**, deployed 2026-09-22 on the CapRover VPS (`x86_64`) as
  `smkamranqadri/tartib:v2.1`: `v2.0` plus slices 30 and 31 and the fixes after it (history.md),
  classifying on the pinned `gpt-5.6-luna` at medium reasoning (checks under Proof). The
  database as it was just before is backed up (`private.md`, Backups); that file and `v2.0` are
  the rollback.
- Task: none in flight. **Slice 33 (links, A to C) is built and verified on `main`**, not deployed;
  phase C ships with `TARTIB_LINK_PROPOSALS` off (`../intent/slice-33-links.md`, Proof).
  **Slice 32 (Pick for me) is built and verified on `main`, not deployed**
  (`../intent/slice-32-pick-for-me.md`, Proof); the owner chose to start 33 before deploying.

## Open

- **Cloudflare still overrides the browser cache on `sw.js`** (`max-age=14400` where the app
  sends `no-cache`; Knowledge, Deploy). Until Browser Cache TTL is set to Respect Existing
  Headers, a new version can take four hours to reach the phone, or a delete and re-add.
- **Not yet seen on the phone:** everything since `v2.0` -- the modals (`<dialog>` on iOS),
  tickable checklists, the first line as the title, the pills. Each was proved in Chrome only.
- **Real data is accumulating on the live database, to be read later.** `ai_calls` records what
  was in each prompt (migration 0017, cannot be backfilled), and `TARTIB_DUPLICATE_PARK` is
  **off**, so duplicate verdicts are recorded while nothing is held back. It should answer
  whether the prompt grows with the database, whether examples are real corrections rather than
  padding, and a real false-positive rate for duplicates. House rules (four) are set since
  2026-09-22, so compare accuracy before and after that date.
- No backups of the deployed database. Deferred by decision on 2026-09-18 and not reopened.

## Next

1. **Deploy slices 32 and 33 as `v2.2`** -- rehearsed on a live snapshot 2026-09-22 through
   migration 0020 (Proof; 0021, one added column, came after): bump `SW_VERSION`, back up the database first
   (`private.md`), `./deploy.sh v2.2`, then check migrations 0019 to 0021 applied, one Pick and
   one link from the phone.
2. **Switch `TARTIB_LINK_PROPOSALS` on** once item 4 is done, and watch the inbox it fills.
3. **Try `v2.1` on the phone** (Open, above), then the backlog (`kis/intent/backlog.md`).
4. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
5. **Answer the four questions** under Known gaps, on `v2.1`.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **340 passed, 9 deselected** (the nine are the evals) and
  **19/19** from `npm run ui`. Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName". The version
  number is a rollback label, and why `v2.0` was not `v1.1` is in `../knowledge/technical.md`,
  Deploy. `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-09-22.3`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

## Proof

Each slice keeps its proof in its plan file and its commits.

**`v2.2` rehearsed on a live snapshot, 2026-09-22 (not deployed):** a read-only backup-API copy
of the live database (schema 18, 196 items, 180 captures) run locally on `main` with AI and push
keys off. Migrations 0019 and 0020 applied: schema 20, integrity ok, no foreign-key faults, every
count unchanged, all 196 items identical in text, `updated_at`, star, status and space; the link
index keyed all 196 (0 links yet, one shared first line). `npm run ui` against it: 18/18 after one
fix -- Home scrolled sideways 12px at 390px, the phone's `.dash` column being a bare `1fr` that
grew to the longest unbreakable line (older than 32 and 33; now `minmax(0, 1fr)`). The snapshot
and every copy were deleted after, here, in the container and on the host.

**`v2.1`, checked 2026-09-22 from outside and in the container:** `/api/health` answers
`{"ok":true,"ai":true}`, `sw.js` is `2026-09-22.3` (purged from Cloudflare by hand), `http://`
answers 302, the login cookie is `HttpOnly; Secure; SameSite=lax`, the container runs `v2.1`,
and migration 0018 applied: schema 18, 43 tasks opening with their title line, as the dry run on
a live snapshot predicted (37 added, 0 `updated_at` moved). **From `v2.0`, reported by the
owner:** push subscribes on the phone and in desktop Safari.

## Known gaps

Offline behaviour that is designed rather than missing -- counts lagging, and text editing
needing one moment online first -- is product truth: `../intent/SPEC.md`, Offline.

- **Four questions only the phone can answer are still open:**
  1. whether mono at 14px suits a long note -- the one decision in slice 23 taken knowingly
     against readability;
  2. whether `background-attachment: fixed` survives iOS;
  3. whether tapping a word is a discoverable way into editing when no button says so -- since
     slice 31 that includes the title, which is now the first line of the text;
  4. whether a debounced autosave feels safe without a Save button to press. Only answerable
     from `v2.1` on: before `c91fbf9` every save reloaded the note in a space's split view, and
     "Saved" never showed.
- The committed UI suite (`npm run ui`, 14 checks) guards slices 22 to 25, 27, 29 and 31, and the
  reload fix and tickable boxes (F1, F2). It cannot judge how anything reads; slices 26 and 28
  are outside it for a stated reason, and slice 30's split card was proved by a scratch script
  and is not in it.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`,
Chromium browsers that cannot reach Google's push service, `pushsubscriptionchange`, the silent
worker at session end, voice capture -- is Knowledge: `../knowledge/technical.md`, "What browsers
do to this app".
