# Current

- Local detail (the domain, backups, subscribed devices, how this Mac reaches `/mcp`) lives in
  `kis/state/private.md`, gitignored and never published. This file points there.
- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, in step with
  it at `d4214a8` when this was written (the `v2.10` tag and GitHub release are on that commit);
  `git log` has the truth.
- **Live: `v2.10`**, deployed by the owner in CapRover on 2026-11-09, `main` and the `v2.10` tag
  pushed at `d4214a8`, GitHub release created. Checked from outside at 2026-11-09T12:55Z against the
  public domain (`private.md`): health `{"ok":true,"ai":true}`; `http://` 302 to `https://`;
  `/mcp` (GET and POST) and `/api/today` 401 without credentials; `sw.js` `SW_VERSION =
  "2026-10-15.1"`; bundle `assets/index-D5v0LKfV.js` (both unchanged, no frontend change). On the
  server the running container's image is `smkamranqadri/tartib:v2.10`, digest
  `sha256:dda390bdd5e80937744ab14739009d2ec9c624238f55f3d1e9f5b20381c91f03`. **Not yet checked on
  live:** `tools/list` = 24 tools and one `today` reply (they need the MCP token), and `pick`
  (it writes, so not without the owner's say). Rollback to `v2.9` is clean (no migration). Release
  records, `v2.9` included, in `../intent/history.md`.
- **Last task: slice 41, `today` and `pick` over MCP**, released in `v2.10`; plan and proof
  `../intent/slice-41-desk-tools.md`.
- **Slice 41 proof, as built:** backend **439 passed, 10 deselected** and `ruff check .` clean (re-run
  by me); a Codex-on-Sol code review found two defects, both fixed and mutation-checked; a real MCP
  client read one reply of each tool against a throwaway server. The CHANGELOG, README,
  `technical.md` and SPEC are written. Nothing is in progress.

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

1. **Check `v2.10` with the MCP token** (24 tools, one `today` reply); the owner decides whether
   `pick` is called on live.
2. **Slice 40, routines** (planned 2026-11-09, Phase mode, five steps, revised after a Sol plan
   review; not built): `../intent/slice-40-routines.md`. Decisions 7 and 8 are confirmed.
3. **Switch `TARTIB_LINK_PROPOSALS` on** once the backlog prerequisites are done -- and first fix "Tell it why" on a
   `linked` item, which ignores the link hold (slice 33's plan, Known).
4. **The backlog** (`kis/intent/backlog.md`): nothing in it is ordered yet.
5. **Judge the duplicate verdicts** once enough real captures carry them, then decide whether to
   switch parking on.
6. **Answer the four questions** under Known gaps, on the live version.

## Commands

- Verify: the full list, and what an eval failure means, is `../knowledge/technical.md`,
  Verification commands. Expect **439 passed, 10 deselected** (the ten are the evals; run pytest from `backend/`, or
  its `-m 'not eval'` default is skipped and the evals call Codex) and **26/26** from `npm run ui` (last run 2026-11-09; see Verification commands for running it on this Linux machine). Any red is real, except S33, which is flaky.
- Deploy: `./deploy.sh vX.Y`, then CapRover's Deployment tab, "Deploy via ImageName" (version
  numbering: `../knowledge/technical.md`, Deploy). `SW_VERSION` in `sw.js` is bumped by hand on every release that changes the bundle;
  it is at `2026-10-15.1`.
- Push keys: `cd backend && uv run python -m tartib.vapid`. Regenerating invalidates every
  subscription; Settings re-mints on the next open.
- Local development: `docker compose up -d --build` against http://localhost:8000.

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
