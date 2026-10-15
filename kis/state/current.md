# Current

- Local detail (the domain, backups, subscribed devices, how this Mac reaches `/mcp`) lives in
  `kis/state/private.md`, gitignored and never published. This file points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, pushed and
  in step with it. The `#378` + `#243` + `#228` + `#281` cycle is merged by two merge commits
  (`ff734b7`, `192f64f`); the owner's later work sits on top, the newest being the search
  snippets (`41d8c63`) and the KIS anchor 0.10.1 (`90ed6ab`). The owner deployed `v2.7` on
  2026-10-15; it is live and verified from outside (below).
- **Live: `v2.7`**, deployed by the owner on 2026-10-15 and verified from outside the same day:
  public health `{"ok":true,"ai":true}`, `http://` answers 302 to `https://`, the served `sw.js`
  says `SW_VERSION = "2026-10-15.1"`, and the page serves the bundle the build produced
  (`assets/index-D5v0LKfV.js`). It carries #378 space descriptions (migration 0025) plus #243,
  #228 and #281. Previous release: `v2.6` (`b230c3d`, checked 2026-10-07). Rollback is `v2.6`
  **on schema 25** - the unproven check below: v2.6 predates migration 0025, so a rollback leaves
  it running against a schema it did not create.
- Task: #378 space descriptions, released in `v2.7` on 2026-10-15. Owner-written description per
  space (500 characters, empty clears, stale-write token), migration 0025, app editor,
  REST, MCP `set_space_description` (eighteen tools), description-aware classification
  capped at 12,000 characters of space context. Plan and decisions:
  `../intent/space-descriptions.md`; verification: `../tartib.reports/space-descriptions/design-handoff.md`,
  "Resume verification". Tartib #378 can be closed now that it is released.
- Release `v2.7`, 2026-10-15: image built and pushed by `./deploy.sh v2.7` as
  `smkamranqadri/tartib:v2.7` (manifest index
  `sha256:10957e4373ef61c3d69fd4e40cb0f3d8b2ae2d92548ba001194eada87a233c75`), `SW_VERSION` bumped
  to `2026-10-15.1`, deployed by the owner the same day. Two checks recorded here as
  prerequisites were **not** run: proving `v2.6` starts and works on schema 25 (rollback), and the
  live described-vs-baseline eval (`-m eval`, needs Codex quota). A phone may still take up to
  four hours to pick this up - Cloudflare rewrites `sw.js`'s `no-cache` to `max-age=14400` (seen
  at this deploy), which is the open item below.
- The rest of the cycle -- #243 Home Needs attention, #228 nav Inbox count, #281 session
  finish sound -- is implemented, merged on main and released in `v2.7`. Verified on the merged tree
  on 2026-10-09: backend 397 passed / 10 deselected, frontend typecheck and build clean,
  `npm run ui` 26/26 with three new checks. Details: `../intent/backlog.md` and
  `../intent/bug-281-session-ring.md`; orchestrator ledger: `../tartib.reports/orch/ledger.md`.
- MCP `search` and `list_items` return id, first line and a snippet, not the whole item
  (`41d8c63`, merged on main 2026-10-14, unreleased; plan `../intent/search-snippets.md`).
  Verified in a clean checkout at `41d8c63`: backend 399 passed / 10 deselected. Ships with `v2.7`.

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
