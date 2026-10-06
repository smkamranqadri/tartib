# Current

- Local detail (the domain, backups, subscribed devices, how this Mac reaches `/mcp`) lives in
  `kis/state/private.md`, gitignored and never published. This file points there.
- Branch: `feature/mcp-find-replace`, from `main` which tracks `origin/main` at
  `https://github.com/smkamranqadri/tartib`; tracks `origin/feature/mcp-find-replace`. Feature
  baseline code commit `8274f4f` is pushed; review fixes and final tool wording are committed locally.
  `v2.5` was deployed from `0695dab`; it remains live and unchanged.
- **Live: `v2.5`**, deployed 2026-09-28 on the CapRover VPS as `smkamranqadri/tartib:v2.5`:
  `v2.4` plus the `set_reminder` MCP tool (sixteen tools; Tartib #247, done). Backend only, no
  migration, `SW_VERSION` unchanged. `TARTIB_LINK_PROPOSALS` off, `/mcp` on. `v2.4` runs on the
  same schema 24 and is the rollback.
- Task: Slice 38 review fixes verified locally: expected count, compact output, explicit scope,
  literal whitespace, accurate stale-check wording and removal of unrelated formatting.
  Revisions are committed locally and not deployed. Tartib #380 remains open (records the baseline).

## Open

- **Cloudflare still overrides the browser cache on `sw.js`** (`max-age=14400` where the app
  sends `no-cache`; Knowledge, Deploy). Until Browser Cache TTL is set to Respect Existing
  Headers, a new version can take four hours to reach the phone, or a delete and re-add.
- **Not yet seen on the phone:** the modals (`<dialog>` on iOS), tickable checklists, the first
  line as the title, the pills, Pick for me, the `[[` picker, slice 36's link cards and slice
  37's thought Edit and Delete. Each was proved in Chrome only.
- **Real data is accumulating on the live database, to be read later.** `ai_calls` records what
  was in each prompt (migration 0017, cannot be backfilled), and `TARTIB_DUPLICATE_PARK` is
  **off**, so duplicate verdicts are recorded while nothing is held back. It should answer
  whether the prompt grows with the database, whether examples are real corrections rather than
  padding, and a real false-positive rate for duplicates. House rules (four) are set since
  2026-09-22, so compare accuracy before and after that date.
- **No scheduled backups** of the deployed database, only a copy before a release with a
  migration, the newest before `v2.4` (`private.md`, Backups). Scheduled ones are in the backlog.

## Next

1. **Review and integrate Slice 38** from `feature/mcp-find-replace` (baseline `8274f4f` plus
   local review-fix commit; not deployed).
2. **Try `v2.5` on the phone**: one Pick, one `[[link]]` with the picker, a thought's Edit and
   Delete, and a link card's Link / No links / Later.
3. **Run the namazee flow over `/mcp`**: pull its tasks, and after the work mark one done with a
   thought.
4. **Switch `TARTIB_LINK_PROPOSALS` on** once item 5 is done -- and first fix "Tell it why" on a
   `linked` item, which ignores the link hold (slice 33's plan, Known).
5. **The backlog** (`kis/intent/backlog.md`): nothing in it is ordered yet.
6. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
7. **Answer the four questions** under Known gaps, on `v2.5`.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **383 passed, 9 deselected** (the nine are the evals) and
  **22/22** from `npm run ui`. Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName" (version
  numbering: `../knowledge/technical.md`, Deploy). `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-09-27.1`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

## Proof

Each slice keeps its proof in its plan file and its commits; releases before `v2.5`, and the
reviews before `v2.2`, are in `../intent/history.md` and git. The pre-deploy rehearsal on a live
snapshot (2026-09-22) found the phone dashboard's 12px sideways scroll (`5405db3`).

**`v2.5`, checked 2026-09-28:** health ok with AI on, `/mcp` 401 without the token and sixteen
tools with it, and `set_reminder` called live with a past time was refused naming the current
time in Asia/Karachi (nothing written).

**`/mcp` writes used for real, 2026-10-01:** `add_note`, `add_thought`, `edit_item` and
`delete_item` rebuilt the owner's `ai-agents` space, backup first (`private.md`, Backups).

**Slice 38 review fixes, verified 2026-10-06, local only:** backend suite **383 passed,
9 deselected**; changed-file Ruff and `git diff --check` passed. Eight guard mutations failed
as expected and source was restored byte-for-byte. Single-line edit response is under 500
characters for a roughly 10,000-character note. No deployment performed.

## Known gaps

Designed offline behaviour is in `../intent/SPEC.md`, Offline.

- **Four phone-only questions remain:** mono at 14px for long notes; fixed background on iOS;
  whether tapping text (including the first-line title) makes editing discoverable; and whether
  debounced autosave feels safe without a Save button. Autosave is judgeable from `v2.1` onward;
  before `c91fbf9`, saves reloaded the split view and never showed "Saved". Details:
  `../intent/slice-26-retrieval.md`.
- What the committed UI suite covers, and what it leaves out, is `../knowledge/technical.md`,
  "Settled in slice 26".

Browser and device limits deploying will not change: `../knowledge/technical.md`, "What browsers do to this app".
