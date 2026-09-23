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
  The first `suggest_links` pass ran on every space 2026-09-23: 194 calls (one timeout, retried),
  67 items sent back with 81 links; all reviewed by the owner (0 waiting before `v2.3`).

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

1. **Try `v2.2` on the phone**: one Pick, one `[[link]]`, and connect Claude Code to `/mcp`
   (`private.md`, MCP). Then, when ready, a real `suggest_links --space infra` run.
2. **Switch `TARTIB_LINK_PROPOSALS` on** once item 4 is done, and watch the inbox it fills.
3. **The backlog** (`kis/intent/backlog.md`): nothing in it is ordered yet.
4. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
5. **Answer the four questions** under Known gaps, on `v2.2`.

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

Each slice keeps its proof in its plan file and its commits.

**`v2.3`, checked 2026-09-23:** health ok, `sw.js` `2026-09-23.2` (purged by the owner), the
production bundle carries slice 36's labels ("No links", "File + link", "Moved “") and the settle,
`http://` 302, cookie `HttpOnly; Secure; SameSite=lax`, the container runs `v2.3`, schema 23,
integrity ok, 196 items; `/mcp` 401 without the token and 11 tools with it.

**`v2.2`, checked 2026-09-23 from outside and in the container:** `/api/health` answers
`{"ok":true,"ai":true}`, `sw.js` is `2026-09-23.1` (Cloudflare purged by the owner; it still sends
`max-age=14400`), `http://` answers 302, the login cookie is `HttpOnly; Secure; SameSite=lax`, the
container runs `v2.2`. Migrations 0019 to 0023 applied: schema 23, integrity ok, no foreign-key
faults, and all 196 items hash identical to the pre-deploy backup (text, `updated_at`, star,
status, space, stage); 196 link keys, 0 links. `/mcp`: 401 with no token, a wrong one, or the
login password; with the token, `initialize` as `tartib`, 11 tools, `list_spaces` 26. In the
container, `suggest_links --space infra --limit 5 --dry-run`: 5 calls, 3 items with 3 links,
nothing stored. `TARTIB_LINK_PROPOSALS` off.

**`v2.2` reviewed before deploy, 2026-09-23 (`ae74c43..HEAD`, three separate agents, read-only):**
code review, security review, and SPEC against the build. No crash, data loss or exploitable hole.
Fixed, each with a test shown to fail without its fix: `suggest_links` dropped a pair whose target
had been sent back earlier in the same run; approving from the item page wrote every proposed
link unseen (absent `links` now keeps none); a card's title edit was lost when a link was kept;
Pick starred a task finished or deleted during its call, or failed with a 500; `[[space: x]]` was
half a link; the service worker cached every picker keystroke; `@codemirror/autocomplete` was
undeclared. Rules 4, 5 and 7 amended to record slices 32, 34 and 35. Known and left: redo ignores
the link hold (switch off; slice 33's plan), the API cache survives sign-out (backlog). After:
370 passed, 9 deselected; `npm run ui` 20/20.

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
- The committed UI suite (`npm run ui`, 20 checks) guards slices 22 to 25, 27, 29 and 31 to 34,
  and the reload fix and tickable boxes (F1, F2). It cannot judge how anything reads; slices 26 and 28
  are outside it for a stated reason, and slice 30's split card was proved by a scratch script
  and is not in it.

Browser and device behaviour that will not change by deploying -- iOS `notificationclick`,
Chromium browsers that cannot reach Google's push service, `pushsubscriptionchange`, the silent
worker at session end, voice capture -- is Knowledge: `../knowledge/technical.md`, "What browsers
do to this app".
