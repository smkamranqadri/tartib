# Current

- Local operational detail -- the domain, the backup paths, which devices are subscribed -- lives
  in `kis/state/private.md`, gitignored and never published. This file carries the substance and
  points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public.
  In step with `origin/main` since 2026-09-23 (pushed after `v2.3` went live).
- **Live: `v2.3`**, deployed 2026-09-23 on the CapRover VPS as `smkamranqadri/tartib:v2.3`:
  `v2.2` (slices 32 to 35) plus slice 36, the link cards. `TARTIB_LINK_PROPOSALS` off, `/mcp` on.
  No migration; `v2.2` and the backup taken just before (`private.md`, Backups) are the rollback.
- Task: none in flight.
- **Links on the live data:** the first `suggest_links` pass ran on every space 2026-09-23 (194
  calls, one timeout retried), sent 67 items back with 81 links, and the owner reviewed them all.
- **Claude Code on this Mac is connected to `/mcp`** at user scope, so every project has the Tartib
  tools (`private.md`, MCP).

## Open

- **Cloudflare still overrides the browser cache on `sw.js`** (`max-age=14400` where the app
  sends `no-cache`; Knowledge, Deploy). Until Browser Cache TTL is set to Respect Existing
  Headers, a new version can take four hours to reach the phone, or a delete and re-add.
- **Not yet seen on the phone:** the modals (`<dialog>` on iOS), tickable checklists, the first
  line as the title, the pills, Pick for me, the `[[` picker and slice 36's link cards. Each was
  proved in Chrome only. The `relink` cards of `v2.2` were used on the phone (the owner approved
  50 there), which is how "Not now" and the jumping list were found.
- **Real data is accumulating on the live database, to be read later.** `ai_calls` records what
  was in each prompt (migration 0017, cannot be backfilled), and `TARTIB_DUPLICATE_PARK` is
  **off**, so duplicate verdicts are recorded while nothing is held back. It should answer
  whether the prompt grows with the database, whether examples are real corrections rather than
  padding, and a real false-positive rate for duplicates. House rules (four) are set since
  2026-09-22, so compare accuracy before and after that date.
- No backups of the deployed database. Deferred by decision on 2026-09-18 and not reopened.

## Next

1. **Try `v2.3` on the phone**: one Pick, one `[[link]]` with the picker, and a link card's
   Link / No links / Later.
2. **Use `/mcp` from a project** (namazee): pull its tasks, and after the work mark one done with a
   thought -- the first real use outside a test.
3. **Switch `TARTIB_LINK_PROPOSALS` on** once item 5 is done -- and first fix "Tell it why" on a
   `linked` item, which ignores the link hold (slice 33's plan, Known).
4. **The backlog** (`kis/intent/backlog.md`): nothing in it is ordered yet.
5. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
6. **Answer the four questions** under Known gaps, on `v2.3`.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **370 passed, 9 deselected** (the nine are the evals) and
  **21/21** from `npm run ui`. Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName". The version
  number is a rollback label, and why `v2.0` was not `v1.1` is in `../knowledge/technical.md`,
  Deploy. `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-09-23.2`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

## Proof

Each slice keeps its proof in its plan file and its commits; releases before `v2.3`, and the
reviews before `v2.2`, are in `../intent/history.md` and git. The pre-deploy rehearsal on a live
snapshot (2026-09-22) found the phone dashboard's 12px sideways scroll (`5405db3`).

**`v2.3`, checked 2026-09-23:** health ok, `sw.js` `2026-09-23.2` (purged by the owner), the
production bundle carries slice 36's labels ("No links", "File + link", "Moved “") and the settle,
`http://` 302, cookie `HttpOnly; Secure; SameSite=lax`, the container runs `v2.3`, schema 23,
integrity ok, 196 items; `/mcp` 401 without the token and 11 tools with it.

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
- The committed UI suite (`npm run ui`, 21 checks) guards slices 22 to 25, 27, 29, 31 to 34 and 36,
  and the reload fix and tickable boxes (F1, F2). It cannot judge how anything reads; slices 26 and 28
  are outside it for a stated reason, and slice 30's split card was proved by a scratch script
  and is not in it.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`,
Chromium browsers that cannot reach Google's push service, `pushsubscriptionchange`, the silent
worker at session end, voice capture -- is Knowledge: `../knowledge/technical.md`, "What browsers
do to this app".
