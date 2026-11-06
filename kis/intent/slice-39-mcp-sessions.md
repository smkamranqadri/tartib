# Slice 39: sessions and due reminders over MCP

Planned 2026-11-05 with the owner. Standard mode. **Built and verified locally 2026-11-06; released as `v2.9` the same day.**
Lifts "sessions" from slice 35's out of scope (`slice-35-mcp.md`).

## What was asked

The owner, in their words: an MCP tool "for starting session and end session or may be a point to
subscribe the event of timer", and asked how an agent can know the server time when the app shows
it. Then, one more: `reminders_due(until)`, returning "open items with a remind_at up to that time,
across all spaces, including ones Tartib already pushed. The desk keeps its own record of what it
spoke, keyed by item id and remind_at."

## Decided with the owner, 2026-11-05

1. **No subscription.** `/mcp` is stateless JSON by design (slice 35: Cloudflare can buffer
   streams, GET answers 405). An agent cannot watch a countdown anyway; it asks. The phone push at
   the end of a session already exists.
2. **Server time is a field in the reply**, not a stream: `server_time`, plus `remaining_seconds`
   while a session runs. The app counts down in the browser against the server's `ends_at`; an
   agent reads the same two facts.
3. **Push on an MCP-started session: yes**, as in the app. Rule 4 covers "a session the user
   started"; the agent starts it for them. No new carve-out. `sw.js` stays silent when the app is
   on screen.
4. **Outcome: an optional argument on `end_session`.** `outcome=done` ticks the task through the
   same write path as `set_status`, so an agent gains no new power.
5. **No provenance.** No `sessions.client`, no migration; rollback stays clean. The countdown bar
   shows in the app at once and Stop is one tap.
6. **`reminders_due` takes an optional `since`.** Without it, every open task with
   `remind_at <= until`, including ones Tartib expired unpushed. With it, a poll passes its last
   `until` and gets only what is new.
7. **"The desk" is an external client of `/mcp`** that dedups on (item id, `remind_at`). Its
   record lives with it; Tartib stores and writes nothing for it. Confirmed by the owner on
   2026-11-05: it is an external MCP client.

## Challenges raised

- **`set_outcome` on a running session** sets `ended_at = ends_at`, in the future, and leaves the
  timer armed. `end_session` must `stop` and `disarm` first, then record the outcome.
- **`due_items` cannot be reused** for `reminders_due`: it filters `reminded_at IS NULL` and
  `remind_at > now - 6h`, and this tool must include pushed and old items.
- **Polling cost.** There is no wait or subscribe tool; the descriptions say to call
  `get_session` once and use `remaining_seconds`, not to loop.
- **Past times.** `set_reminder` rejects a past time; `reminders_due` must accept one, so it needs
  its own parser, not `_moment`.
- **Unattended starts.** An agent can start a session without being asked; the server
  instructions say not to start one unasked.

## Build

Four tools in `backend/tartib/mcp_server.py`, reusing `sessions.py`. The scheduler is
`app.state.sessions`, so the end-of-session push works as in the app.

- `start_session(item_id?)`: `sessions.start` + `Sessions.arm`. Refused with the existing text
  while one runs (409) or for an unknown item (404), as `ToolError`.
- `get_session()`: `running`, then `awaiting`, else none, plus the item, as `/api/sessions/current`.
- `end_session(outcome?)`: stops and disarms the running session; with `outcome`, records it.
  With nothing running, `outcome` answers the one awaiting. Nothing running or awaiting is an
  error. A repeated outcome is refused.
- Every session reply carries `started_at`, `ends_at`, `server_time` (UTC ISO) and, while
  running, `remaining_seconds` (a snapshot at read time).
- `reminders_due(until, since?)`, read-only, across all spaces:
  `stage='filed' AND status='open' AND remind_at IS NOT NULL AND remind_at <= until
  [AND remind_at > since]`, `ORDER BY remind_at, id`, `LIMIT 100`. No `reminded_at` filter.
  Per item: `id`, `space`, `first_line`, `remind_at` (the stored UTC `...Z` string, unchanged),
  `reminded_at`, `due`, `starred`. Reply: `{server_time, until, since, items, truncated}`.
  `until` inclusive, `since` exclusive. Times are ISO 8601, no offset read in `TARTIB_TZ`, past
  allowed; `until < since` or a bad time is a `ToolError`.
- Moving a reminder changes `remind_at`, so it is a new key for the desk and speaks again, as
  `store.py` already re-arms `reminded_at` on a real change.
- Server instructions gain: call `get_session` before starting; the session is the owner's, do
  not start one unasked; do not poll in a loop; pass `since` to `reminders_due`.

## Out of scope

Subscribe, SSE and resource subscriptions; any migration or `sessions.client`; attaching a task to
a running session (backlog); nudges for forgetting to run a session (backlog; rule 9); marking a
reminder spoken; tracking the desk's record in Tartib; a local-time field; any change to the app
UI, push rules or session length.

## Acceptance

1. `tools/list` shows 22 tools including the four; `/mcp` is still 401 without the token.
2. `start_session` returns `started_at`, `ends_at`, `server_time` and `remaining_seconds` near
   1500; a second start is refused with "already running".
3. `start_session(item_id)` for an unknown item is refused; a known one shows in `get_session`'s
   item.
4. `get_session` returns running, then awaiting after `end_session` without an outcome, then none
   after an outcome.
5. `end_session` stops a running session with `ended_at` about now (not `ends_at`) and cancels
   the pending push.
6. `end_session(outcome="done")` on a task-linked session ticks the task; `unfinished` and
   `abandoned` do not.
7. A repeated outcome is refused; `end_session` with nothing running or awaiting is refused.
8. A started session pushes once at `ends_at` (injected sender), and not after an early end.
9. Open tasks with `remind_at <= until` come back across two spaces, oldest first.
10. An item with `reminded_at` set (already pushed) is returned, with `reminded_at` shown.
11. Done tasks, notes, unfiled items and tasks with no `remind_at` are not returned.
12. `since` excludes `remind_at <= since`; polling with `since` = the previous `until` repeats
    nothing.
13. `remind_at` in the reply equals the stored string byte for byte; a moved reminder shows the
    new value.
14. 101 matches give 100 items, `truncated: true`, and they are the oldest 100.
15. A naive `until` is read in `TARTIB_TZ` (tested in a non-UTC zone); `until < since` and a
    malformed time are refused.
16. Calling `reminders_due` changes nothing: `reminded_at` and `updated_at` are identical before
    and after.

## Verification

- `pytest` in `test_mcp.py`, the SDK's own client over HTTP against the app, with an injected
  clock and sender for the push. Expect 399 plus the new tests passed, 10 deselected; `ruff` clean.
- Mutation checks, each restored from a saved original and proved byte-identical: drop `disarm`
  in `end_session` (checks 5, 8 fail); drop `stop` before `set_outcome` (check 5 fails); add
  `reminded_at IS NULL` to `reminders_due` (check 10 fails); drop the `status` filter (11); order
  DESC (9, 14); make `since` inclusive (12).
- One real client: Claude Code against a throwaway Tartib with its own token and database, running
  start, get and end once, and `reminders_due` once. Delete everything afterwards.
- A short self-review of the endpoint: no new auth path, but `/mcp` is a credential surface.

## On ship

`technical.md`: the MCP tool list and the session and `reminders_due` semantics. `slice-35-mcp.md`:
its "Out of scope: sessions" points here. `current.md`: the task, proof, and the drift fixed at
sync (`SW_VERSION`, test counts, the v2.8 line about vulnerability reporting and `docs/api.md`).
`history.md`.

## Proof (2026-11-06, local, uncommitted tree on top of `ffefc03`)

- `uv run pytest -q` from `backend/`: **410 passed, 10 deselected** (399 before; eleven new in
  `test_mcp.py`, covering acceptance 1 to 16). `uv run ruff check .` clean. `ruff format` was not
  applied: the repo's existing code is not formatted to it, and only the lint gate is used.
- A test caught a real fault while building: `remaining_seconds` used the unrounded clock while
  `server_time` was whole seconds, so `ends_at - server_time` said 1500 and the tool said 1499.
  Fixed in the code (one instant for both), not in the test.
- Mutation checks, each a literal edit with the file restored and `cmp`-identical after: no
  `disarm` (the push test fails); no `stop` before the outcome (three tests fail, including the
  `ended_at <= server_time` assertion); `reminded_at IS NULL` added (two fail); `status` filter
  dropped (one); `ORDER BY ... DESC` (three); `since` inclusive (one); `truncated` forced false
  (one); the whole-second fix removed (one). All eight failed the test meant to catch them.
- **A real client**: Claude Code 2.1.310, headless (`claude -p`, Haiku 5.5, low effort, a throwaway
  `--mcp-config`, nothing saved) against a throwaway Tartib on port 8002 with its own token and
  database. It called `get_session`, `start_session` on a task, `get_session`, `end_session`
  with `unfinished`, and `reminders_due` with a naive `until`. Checked in the database
  afterwards, not from the client's report: one session, `ended_at` 2 seconds after `started_at`
  (before `ends_at`), outcome `unfinished`, task still open, `notified_at` empty; both reminders
  untouched. The client ran `get_session` in parallel with `end_session` once and said so; that
  is agent ordering, not a fault. Throwaway server, token and database deleted.
- **Self-review**: no new auth path; the four tools sit behind the same `TokenGuard`, and
  `reminders_due` reads what `list_items` across spaces already could. The one write path that
  matters, `end_session(outcome="done")`, is the same update `set_status` makes.
- **Not verified**: the push to a real phone from an MCP-started session (the injected sender
  proves one `broadcast`, once, and none after an early end); the live deploy; `npm run ui`
  (no UI changed).

## Status
- [x] session tools (start, get, end) with tests
- [x] `reminders_due` with tests
- [x] mutation checks, real client, self-review
- [x] KIS sync (Knowledge, State, slice 35 pointer)
- [x] README, CHANGELOG, `history.md`; committed as `v2.9`
- [x] deployed 2026-11-06; live `tools/list` shows 22 (State, Live)
