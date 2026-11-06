# Current

- Local detail (the domain, backups, subscribed devices, how this Mac reaches `/mcp`) lives in
  `kis/state/private.md`, gitignored and never published. This file points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, in step with
  it at `878aa3b` (the `v2.9` tag and GitHub release are on that commit); `git log` has the truth.
- **Live: `v2.9`**, deployed by the owner in CapRover on 2026-11-06 and checked from outside at
  2026-11-06T04:25Z: health `{"ok":true,"ai":true}`; `http://` 302 to `https://`; `/mcp` and `/api`
  401 without credentials; `sw.js` `SW_VERSION = "2026-10-15.1"`; bundle `assets/index-D5v0LKfV.js`
  (unchanged, no frontend change); and an authenticated MCP client read `tools/list` = **22 tools**
  including the four new ones, with the server instructions naming `get_session` and
  `reminders_due`, and `reminders_due(until=2000-01-01)` returned an empty list. That last pair is
  what tells v2.9 from v2.8. Image `smkamranqadri/tartib:v2.9`, manifest index
  `sha256:4c6c84378512adda36bedbcb441c2f8ac85475d15ce134d8c273b44abe85c043`. **Not checked on
  live:** a real phone push from an MCP-started session, and `start_session` / `end_session` themselves (they write; proved locally and with a
  real client against a throwaway server, `../intent/slice-39-mcp-sessions.md`). Rollback to
  `v2.8` is clean (no migration); to `v2.6` it is unproven (schema 25). Previous release `v2.8`
  (`sha256:71b12f96a642b01992e5d350100a733e986aa70534be97f6bc77be2c5751097e`); release records
  in `../intent/history.md`.
- **Last task: slice 39, MCP session tools and `reminders_due`**, released in `v2.9`; plan and
  proof `../intent/slice-39-mcp-sessions.md`. Nothing is in progress; pick from Next.

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
4. **Answer the four questions** under Known gaps, on the live version.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **410 passed, 10 deselected** (the ten are the evals; run pytest from `backend/`, or
  its `-m 'not eval'` default is skipped and the evals call Codex) and **26/26** from `npm run ui` (last run 2026-10-09; not rerun for slice 39, which has no UI). Any red is real.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName" (version
  numbering: `../knowledge/technical.md`, Deploy). `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-10-15.1`.
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
