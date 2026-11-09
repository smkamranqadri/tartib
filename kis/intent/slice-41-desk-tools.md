# Slice 41: `today` and `pick` over MCP, for the desk agent

Planned 2026-11-09 with the owner. Standard mode. **Built, reviewed, committed and deployed as `v2.10` on 2026-11-09.** Revised the same day
after a plan review by Codex on Sol (eight findings, all taken; see the section near the end).
Numbered 41 because slice 40 is routines (`slice-40-routines.md`); the classifier-proposes-rules
slice becomes 42. Builds on slice 39 (`slice-39-mcp-sessions.md`), whose conventions it follows.

## What was asked

A server on the owner's PC (the desk agent, phase 3 of their desk timer) calls `/mcp`. It already
uses `get_session`, `start_session` and `reminders_due`. It asks for two more tools. The owner
pasted the request on 2026-11-09; its content is decisions 1 to 8 below.

## Decided with the owner, 2026-11-09

1. **No second token, no scopes.** The request assumed a scoped desk token. None exists: `/mcp`
   has one token (`TARTIB_MCP_TOKEN`) that opens all tools. The owner chose not to build one. The
   desk keeps using that token, which has full power; the owner tells the desk.
2. **`today` (read only, no arguments).** The open tasks the Today view lists, across all spaces,
   in the Today view's order, at most 20. Reply `{server_time, items, truncated}`; each item is
   `{id, space, first_line, due, starred, remind_at}`. Tasks only; no notes, no done tasks. An
   empty Today is `items: []`, not an error. It writes nothing and leaves `reminded_at` alone.
   The description says to call it once and wait, not in a loop (as `get_session` says).
3. **Time formats follow `reminders_due`, unchanged.** `server_time` and `remind_at` are UTC with
   a `Z`. **`due` is the plain calendar date** (`"2026-11-09"` or `null`), because a task's `due`
   has no time of day; the request asked for a UTC time, and the owner said to do what the other
   tools do. `first_line` is the title, cut at 120 characters (`FIRST_LINE_MAX`).
4. **Order: one shared sort, and the browser sort stays.** The Today view orders in the browser
   (`Home.tsx` `rank`): starred, then overdue, then due later, then no due; ties by due date, then
   id. The server query orders differently. The shared query (`today_rows`) now sorts the same
   way, so `/api/today`, `today` and Pick's prompt agree. The browser compares a missing due as an
   empty string, so among starred tasks one with no due date comes **first**; in the other ranks
   the due date already decides (no-due tasks are rank 3). The server copies that exactly.
   Corrected 2026-11-09: step 1 was first built as "no due last" and did not match the screen. The browser sort stays, for live reordering after a local star or
   tick, and does nothing on data that is already in order. An existing order assertion in
   `test_queries.py` pins the old order; it is updated on purpose, not bent to fit.
5. **`pick` (write, no arguments)** does exactly what `POST /api/pick` does: stars up to three open
   tasks and writes `Picked for today: <reason>` as a thought on each. Reply: the same shape as
   `today`; `items` lists only the tasks this call starred, each `starred: true`. Finding none, or
   the picked tasks changing meanwhile, is `items: []`, not an error. The REST route has three
   different outcomes and the tool maps each one on purpose:

   | Outcome of the route | The tool returns |
   |---|---|
   | Nothing to pick: every open task is already on Today (success with a message) | `items: []` |
   | The picked tasks changed meanwhile (success with a message) | `items: []` |
   | AI failed, reply unusable, or the reply named no candidate (502); AI off (503) | `isError`, short text |

   "Stars nothing" on a failure means precisely this: every item row and thought row is exactly as
   before, so earlier picks keep their stars. Only the `ai_calls` and quota records may be written.
6. **Synchronous, and the desk keeps its 10-second wait.** The live database holds seven real
   Pick calls, all 2026-09-23 to -26 and all successful: 7.2, 7.3, 8.8, 9.0, 13.3, 13.3 and 17.6
   seconds, median 9.0 (read 2026-11-09, `v2.9`, read-only). Three of seven are over ten seconds.
   The owner chose to try 10 seconds and see whether a problem appears. A timed-out call may still
   finish on the server and star tasks; the desk only calls `pick` when Today is empty, so it
   should call `today` next, not `pick` again.
7. **No marker on the thought.** Nothing identifies the desk without a second token, and the
   thought text is how the app recognises a pick. Slice 39 also chose no provenance.
8. **Release.** The owner deploys and tells the desk; the handover text is not kept in the repo
   (owner's call, 2026-11-09). The desk then reads one real reply of each tool to build its parser.

## Challenges raised

- Changing the shared sort changes Pick's "already on Today" list order and `/api/today`'s JSON
  order, and breaks one existing assertion. Ties and a missing due date must be pinned by tests,
  and so must the date boundary between the browser's day and the server's.
- Pick's logic is a route that raises `HTTPException`. It moves into one function that the route
  and the tool both call; the route keeps its status codes and messages, the tool turns the
  failures into `ToolError`.
- **A disconnect may not cancel a pick.** `/mcp` answers with plain JSON, so a client that gives
  up need not stop the handler, and `codex.py` kills its child only on its own timeout. This is
  settled with a test before Pick is extracted (step 3).
- Pick's prompt lists at most 100 candidate tasks (`candidates` stops there), while the Today
  query has no cap. The cap of 20 belongs to the `today` tool only.
- Pick still gets slower as the database grows, up to that 100-task limit, so 10 seconds will fail
  more often over time.
- Two `pick` calls at once: the second takes back the first's stars. This is existing behaviour
  and stays.
- The desk PC holds a full-power token. The owner accepted this on 2026-11-09.

## Scope

**In:** the two tools, the shared sort, the extracted Pick function, the tool count (22 to 24) and
the server instructions text, README, CHANGELOG, and `technical.md` (MCP section) after the build.
**Out:** a scoped token; a marker on the thought; start-and-poll for Pick; any change to `Home.tsx`
or the Pick prompt wording; notes in `today`; a `since` or paging argument.

## Steps

1. **Shared sort.** `today_rows` orders by the browser's rank. Tests pin it to the same cases as
   `rank` in `Home.tsx`, including ties, no due date and the date boundary. The old assertion in
   `test_queries.py` is updated. `/api/today` and Pick's "already on Today" list are re-checked.
2. **`today` tool.** The tool, its description, the server instructions, the tool count. The
   no-write test lands here.
3. **Disconnect and cancellation test.** A sleeping fake Codex and a process check show what
   happens when the client goes away mid-call. If the child survives, fix it here, before Pick is
   touched.
4. **Extract Pick, then the `pick` tool.** One function; the route keeps its codes; the tool maps
   the three outcomes. Existing Pick tests stay green and unchanged.
5. **Docs and samples.** README, CHANGELOG, KIS. One real reply of each tool, from a real MCP
   client against a throwaway server, shown in the build report.

## Acceptance checks

1. `tools/list` returns 24 tools, including `today` and `pick`, and the instructions name them.
2. `today` returns starred first, then overdue, then due later, then no due; ties by due date,
   then id; among starred tasks, one with no due date first, as in the browser. The same cases pass
   against the browser rule and the server rule.
3. `today` omits notes, done tasks, and tasks not filed; includes a task worked on in a session
   today; returns `items: []` when Today is empty. At 20 tasks `truncated` is false; at 21 it is
   true and 20 are returned. `/api/today` and Pick still see every Today row.
4. `today` writes nothing: a trace of every write during the call, with the reminder loop and
   session timers isolated, shows none, and a before-and-after comparison of every table agrees.
   Expired sessions and unreminded items are seeded so a stray write would show.
5. Each item has exactly `id`, `space`, `first_line`, `due`, `starred`, `remind_at`. `due` is a
   valid plain date or `null`; `remind_at` and `server_time` are valid UTC times ending in `Z`
   (or `null`); `first_line` is at most 120 characters.
6. `pick` stars at most three, writes one `Picked for today:` thought on each, and its reply lists
   exactly those tasks, read fresh from the database, with `starred: true`. A second run takes back
   the first run's stars. A mix of stale and valid choices stars only the valid ones.
7. `pick` returns `items: []` for each of the first two outcomes in decision 5, and `isError` for
   the third and for AI off. After each failure every item and thought row equals its seeded
   earlier-pick state; only `ai_calls` and quota rows may change.
8. `POST /api/pick` keeps its statuses (503, 502) and messages.
9. A client disconnect during a pick leaves no Codex process running, or the plan's step 3 fixed
   that before step 4 began.
10. A real MCP client reads one reply of each tool against a throwaway server.
11. The full backend suite stays green (410 passed, 10 deselected, plus the new tests) and
    `npm run ui` stays 26/26.

## Verification method

Backend tests with a fake Codex. `fake_codex.py` steers on classification today, so `pick` gets
its own fake replies (success, empty choice, stale choice, failure, sleeping). Unit tests for the
sort. Mutation check each guard, restored byte-identical: the 20 cap and the 21st-item
`truncated`, the sort key, the no-write guarantee in `today`, the star-nothing-on-failure path and
the stale-choice filter. A real MCP client against a throwaway server, as in slice 39. `npm run
ui` after the sort change. Code review before commit by Codex on Sol in its own visible pane. The
owner deploys; I verify from outside afterwards (tool count 24, and one authenticated `today`
call, which writes nothing). `pick` is not called on the live server without the owner's say,
because it writes.

## Risks and assumptions

- The 10-second wait is likely to fail on about 3 calls in 7 (seven samples, six weeks old).
- Rollback to `v2.9` is clean: no migration.

## Plan review, 2026-11-09

Codex on Sol, high effort, read-only and static (no test was run). Eight findings, all taken. One
was disputed in part: the review said `get_session` can write expired sessions, but `today`
does not run it; `today_rows` and `counts_today` were read and only run `SELECT`.

| Finding | Where it went |
|---|---|
| Shared sort breaks an assertion; ties and null due loose | Decision 4; step 1; checks 2, 3 |
| "Prompt lists every candidate" is wrong (cap 100) | Challenges; check 3 |
| Pick has three different empty outcomes | Decision 5 table; check 7 |
| "Stars nothing" is imprecise | Decision 5; check 7 |
| No-write test could miss writers | Check 4 |
| A disconnect may not cancel Pick | Challenges; step 3; check 9 |
| Fake Codex steers Pick as classification; exact fields unchecked | Verification method; check 5 |
| Step 3 too big | Steps split into five |

## Built and proven, 2026-11-09

Steps 1 to 5 done by Claude Sonnet agents, committed on `main`, released as `v2.10`. Checked
from outside after the deploy: `kis/state/current.md`. Backend suite after the last fix: **439
passed, 10 deselected**, `ruff check .` clean (re-run by me). The `/mcp` tool count is 24.

- **Disconnect (check 9):** a client that leaves does not cancel the handler, on the REST route
  or through MCP; the Codex child runs on and exits by itself, and the pick still lands. Cancelling
  the call did leak the child, so `codex.py` now kills and reaps it on `CancelledError`, and
  tolerates a child that already exited. Nothing cancels the call today; it matters if a server
  shutdown ever does.
- **Changed-meanwhile:** the route's existing behaviour stands: the earlier pick's stars are taken
  back and none are given, and the tool returns `items: []`.
- **Real replies** (Claude Code headless against a throwaway server, fake Codex, fictional tasks):
  `today` returned three items with `due` as a plain date and `remind_at` null; `pick` returned two
  starred items. Both carry `server_time` and `truncated: false`.
- **Code review:** Codex on Sol, high effort, read-only. Two defects (P2 cancel after exit, P3 a
  test that passed without the kill), both fixed with mutation checks. It did not run the full
  suite; I did.
- **Open:** CHANGELOG entry and `technical.md` are written at release time. The UI suite was not
  rerun after step 1 because no frontend file changed.
