# Slice 32: Pick for me

Planned 2026-09-22 with the owner. Standard mode: one migration, one endpoint, one modal.
**Built and verified 2026-09-22 (below, Proof); deployed as `v2.2` on 2026-09-23.**

## What was reported

- **Today is empty** (owner): *"today is empty because it target two things, due date and
  start"* -- "start" meant the star. Today lists open tasks due or overdue, starred, with a passed
  reminder, or worked on in a session today (`queries.py`, `today`), and on the owner's data
  nothing currently meets those.
- **The ask** (owner): *"a ai with run on demand to pull things up from me to work."*

## Decided with the owner, 2026-09-22

1. **A Pick for me button, always in Today's header.** It opens a modal with an optional one-line
   steer ("2 hours, low energy") and Pick. On an empty Today the empty message points to it.
2. **The pool is open filed tasks not already on Today.** The model is also shown what is on
   Today, as context for the day. **Notes are out**: the owner will think about notes separately
   (backlog).
3. **A pick is a star**, up to 3 per run. Offered holding picks for the day and suggestions only;
   the owner chose starring.
4. **A run replaces the previous run's stars.** Offered expiring at midnight; the owner chose
   replace-on-rerun. Consequence accepted: picks not re-run stay starred, and stay on Today.
5. **A star you set is yours.** Any star set by hand, even on a task the AI picked, is never
   removed by a later run.
6. **The reason goes into the item's Thoughts** as `Picked for today: <reason>`. Offered a
   day-only line on the row; the owner chose the thought. Consequence: thoughts are append-only,
   so a task picked often collects entries, and Ask, search and briefs read them.

## Build

- **Migration 0019:** `items.picked_at TEXT NULL`. Set by a pick. Cleared by any `starred`
  change through the item PATCH (`items.py`), which is what makes a hand-set star yours.
- **`POST /api/pick {steer?}`** in a new `backend/tartib/pick.py`:
  - candidates: `stage = 'filed' AND shape = 'task' AND status = 'open'` and not in Today's set
    (reuse the `today` conditions rather than restate them); Today's items listed as context;
  - candidates shown as `t1`, `t2`, ... never ids, as duplicates are (slice 28), so an invented
    label resolves to nothing;
  - `codex.run_json` with a schema of `{picks: [{label, reason}]}`, at most 3; recorded by
    `store.record_call` with its own kind;
  - only after a valid reply, in one transaction: unstar every item with `picked_at` set and
    clear it, star the picks with `picked_at = now`, append one thought each;
  - a failed call, a bad reply or an exhausted quota changes nothing and says why, the quota
    reading shown as Ask shows it (slice 29);
  - no candidates: answer so without calling the model.
- **UI** (`App.tsx`, `api.ts`): the button in Today's header, the modal (slice 31's `<dialog>`
  pattern), Today reloading on success; the empty state names the button.

## Out of scope

Notes in the pool; an AI star that looks different from a hand-set one; picks expiring at
midnight; house rules in this prompt (they are filing rules; the steer does this job); Pick from
the ask bar.

## Acceptance

1. A run stars at most 3 open tasks, none already on Today, each with one
   `Picked for today:` thought.
2. A second run unstars the first run's picks and leaves hand-set stars alone.
3. Unstarring and re-starring a pick by hand makes it survive the next run.
4. An invented label or malformed reply changes nothing and shows an error.
5. An exhausted quota changes nothing and shows the quota message.
6. On an empty Today, Pick fills it.

## Verification

- `pytest`: 308 plus the new `test_pick.py` (fake Codex), all green, evals still deselected.
- `npm run ui`: 14 plus one check for the button, modal and refilled Today.
- One real call on `gpt-5.6-luna` against a local copy before deploy -- one call, not an eval run.
- Review the migration and the transaction before deploy.

## On ship

SPEC's Home line gains Pick for me; `technical.md` gains `picked_at` and the new `ai_calls`
kind; history.md gets the slice; `SW_VERSION` is bumped.

## Proof (2026-09-22, local)

- `uv run pytest -q`: **315 passed, 8 deselected** (308 plus seven in `test_pick.py`, covering
  acceptance 1 to 5 and the no-candidates and AI-off cases); `ruff check`: clean. Five older tests
  asserted schema 18 and were moved to 19, as each migration before did.
- `npm run ui` against the rebuilt local app: **15/15**, the new check S32 stubbing `/api/pick` at
  the network (a UI run must not spend quota) and seeing the modal, the steer sent and the picked
  task on Today (acceptance 6). `tsc --noEmit` clean.
- Looked at on a 390px phone and at 1280px: the button sits in Today's header beside the count,
  44px tall on the phone, and the modal fits both.
- **One real call** on `gpt-5.6-luna`, local app, steer "about two hours this evening": 13.0s,
  23 candidates, 4346 prompt chars, 14764 input and 238 output tokens, recorded as `pick`, ok.
  It picked 2 of 3 allowed -- an undated Play Store task and flights due 2026-10-03 -- each with
  a plain one-line reason.
- Review: self-review only, no separate reviewer ran. A task deleted between the read and the
  write makes the thought insert fail and the whole pick roll back as a 500; accepted as rare.
- As built, differing from Build above: the mark is cleared in `store.update_fields`, not
  `items.py`, so every path that writes `starred` hands the star over; the UI is
  `components/PickForMe.tsx` in `screens/Home.tsx`, not `App.tsx`; and a task Today holds only
  because the last pick starred it is a candidate again (`today_rows(without_picks=True)`),
  which the plan did not say and a re-run needs.
