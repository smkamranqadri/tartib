# Current

- Local detail (the domain, backups, subscribed devices, how this Mac reaches `/mcp`) lives in
  `kis/state/private.md`, gitignored and never published. This file points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`.
  The `#378` + `#243` + `#228` + `#281` cycle is merged on main by two merge commits, tip
  `192f64f` (not pushed). Not deployed: `v2.6` is live and the owner has not released.
- **Live: `v2.6`**, deployed by the owner and checked 2026-10-07 as
  `smkamranqadri/tartib:v2.6`, code `b230c3d`: Slice 38 find_replace, seventeen MCP tools.
  Backend only; no migration or service-worker change. Rollback is `v2.5` on schema 24.
- Task: #378 space descriptions done on main, unreleased. Owner-written description per
  space (500 characters, empty clears, stale-write token), migration 0025, app editor,
  REST, MCP `set_space_description` (eighteen tools), description-aware classification
  capped at 12,000 characters of space context. Plan and decisions:
  `../intent/space-descriptions.md`; verification: `../tartib.reports/space-descriptions/design-handoff.md`,
  "Resume verification". Tartib #378 stays open until released.
- Before releasing the cycle (as `v2.7`): prove `v2.6` starts and works on schema 25
  (rollback); run the live described-vs-baseline eval once Codex quota returns
  (`backend/tests/test_space_descriptions_eval.py`, `-m eval`); bump `SW_VERSION` by hand.
- The rest of the cycle -- #243 Home Needs attention, #228 nav Inbox count, #281 session
  finish sound -- is implemented and merged on main, unreleased. Verified on the merged tree
  on 2026-10-09: backend 397 passed / 10 deselected, frontend typecheck and build clean,
  `npm run ui` 26/26 with three new checks. Details: `../intent/backlog.md` and
  `../intent/bug-281-session-ring.md`; orchestrator ledger: `../tartib.reports/orch/ledger.md`.

## Open

- **Cloudflare still overrides the browser cache on `sw.js`** (`max-age=14400` where the app
  sends `no-cache`; Knowledge, Deploy). Until Browser Cache TTL is set to Respect Existing
  Headers, a new version can take four hours to reach the phone, or a delete and re-add.
- **Real data is accumulating on the live database, to be read later.** `ai_calls` records what
  was in each prompt (migration 0017, cannot be backfilled), and `TARTIB_DUPLICATE_PARK` is
  **off**, so duplicate verdicts are recorded while nothing is held back. It should answer
  whether the prompt grows with the database, whether examples are real corrections rather than
  padding, and a real false-positive rate for duplicates. House rules (four) are set since
  2026-09-22, so compare accuracy before and after that date.
- **No scheduled backups** of the deployed database, only a copy before a release with a
  migration, the newest before `v2.4` (`private.md`, Backups). Scheduled ones are in the backlog.

## Next

1. **Switch `TARTIB_LINK_PROPOSALS` on** once the backlog prerequisites are done -- and first fix "Tell it why" on a
   `linked` item, which ignores the link hold (slice 33's plan, Known).
2. **The backlog** (`kis/intent/backlog.md`): nothing in it is ordered yet.
3. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
4. **Answer the four questions** under Known gaps, on `v2.6`.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **397 passed, 10 deselected** (the ten are the evals; run pytest from `backend/`, or
  its `-m 'not eval'` default is skipped and the evals call Codex) and **23/23** from `npm run ui`. Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName" (version
  numbering: `../knowledge/technical.md`, Deploy). `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-09-27.1`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

## Proof

**MCP task flow, 2026-10-07:** owner confirmed ongoing use across multiple
projects. Open Namazee tasks were independently read through MCP in this session;
completion and thought writes are owner-reported proof from their existing use.

**Phone check, 2026-10-07:** owner reported "all working" after the v2.6 phone
checklist (Pick, `[[` picker and links, thought Edit/Delete, link-card actions where
available, modals, checklists, titles and pills). Owner-reported manual proof; no
independent device probe or confirmation that link proposals were enabled.

Slice 38's local tests and mutation checks are in `../intent/slice-38-find-replace.md`;
older releases and checks are in `../intent/history.md`.

**v2.6 live check, 2026-10-07:** running container image confirmed over SSH; public health
returned ok=true, ai=true. Authenticated MCP lists 17 tools; find_replace description matches
owner wording, server instruction recommends expected=1, and schema exposes expected and scope.
A mismatched expected count was refused; get_item before/after was identical. One successful
replacement ran on production the same day (ai-agents start-here note, expected=1, about 700
characters returned with only the changed line). Build log records image digest
`sha256:c8e48ab633c0a61e193a910177b24f9bc5896c500f5156494d04dd37b9a5a358`.

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
