# Slice 40: routines, a repeat rule on a task

Planned 2026-11-09 with the owner. Phase mode. **Planned, not built.** Revised the same day after
a plan review by Codex on Sol (seven findings, all taken; see the last section).
Takes the "Routines" entry out of `backlog.md`. The classifier half is slice 42, out of scope here.

## What was asked

The owner wants routines as the next building block beside notes, tasks and reminders. Their
examples: check email daily, enter expenses daily, medicine twice a day, a water change in the
battery monthly, a doctor appointment monthly. The old Routine note (backlog entry) adds
"1st Monday / Tuesday / Wednesday of the month" groups with checklists. They also want a record of
each occurrence, done or missed, for streaks.

## Decided with the owner, 2026-11-09

1. **A repeat rule on a task, not a new item type.** A reminder is a field on a task, and a routine
   follows it. The task keeps its checklist, `due`, reminders and links.
2. **Five rule kinds:** daily; weekly on chosen weekdays; monthly on a date (a 31st clamps to the
   month's last day); the nth weekday of the month (1st to 4th); the last weekday of the month,
   read as "the last Friday", not "the last working day". No every-N-days, no yearly.
3. **One reminder time per routine.** "Twice a day" is two daily routines. `remind_at` is stored
   in UTC, so it moves in `TARTIB_TZ`: convert to local time, keep the local time of day on the new
   due date, convert back. A local time that does not exist that day (a clock change) moves to the
   next valid minute. The tick clears `reminded_at`.
4. **Strict skip with a log.** A tick counts for the latest occurrence on or before the day it was
   made; occurrences before it that were still open are logged `missed`; `due` moves to the next
   occurrence after it. A tick before the due date counts for that due date, logged early. An
   occurrence stays open until the next one arrives, so a late tick on a monthly routine is done,
   not missed. The table below is the contract. **A tick names the occurrence it saw** (`for_due`):
   the server applies it only if the routine's `due` still equals `for_due`; otherwise it changes
   nothing and returns the current state. A retry, a double tap, a lost reply and a second device
   therefore cannot tick twice. `routine_log` is also unique on (item, occurrence date).
5. **Stop repeating** clears the rule and keeps the log; the task becomes a plain open task. A
   routine's status stays `open` for its whole life. A tick from the UI, the API, MCP
   `set_status done`, or a session ending `done` is one action through one shared write function.
   **No pause.**
6. **Undo last tick.** Every tick stores a snapshot (`routine_ticks`: the old `due`, `remind_at`,
   `reminded_at` and text) and tags every log row it wrote with the tick's id. Undo restores the
   snapshot and deletes all rows of that tick, however many (rows 2, 4 and 6 write several). Only
   the latest tick of a routine can be undone, and it is refused once the item has changed since
   (any later edit). Undo restores the old `reminded_at` with the old `remind_at`, so it sends no
   duplicate push. (Added by the owner at approval.)
7. **Ticking resets the item's checklist boxes**, on the server, in the same transaction: only the
   box marker changes (`[x]` and `[X]` to `[ ]`), for the list markers `-`, `*`, `+` and `1.`, at
   any nesting, and never inside fenced or inline code. The server must count a box exactly as
   `markdown.ts` does; one shared set of test texts runs against both. Confirmed by the owner.
8. **Setting a rule on a task with no due** sets `due` to the first matching date on or after
   today. Confirmed by the owner.
9. **Where it shows.** Item page: Repeat control, current streak, best streak, a strip of the last
   30 occurrences (done, missed, not yet due). Rows everywhere: "↻ daily" or "↻ 1st Wed" in the
   meta line, no streak numbers. **A Home Routines card owns routines**: one line per routine for
   today (unticked if due or overdue, ticked if done today), repeat label, streak, header "3 of 5
   done today", due ones first, tickable, hidden when there are none. **Today and Pick for me
   exclude routines.** On a phone the card sits after Today.
10. **Offline ticks work.** The queued tick carries `ticked_on`, the date in `TARTIB_TZ` when it
    was made, and `for_due`. The server uses `ticked_on` to choose the occurrence, refuses a future
    date, and replays queued ticks of one routine in order. **Routine ticks are their own queue
    entries**, never merged into the per-item edit entry: edits merge per item and skip conflicts,
    which cannot keep ticks in order beside text edits. Replay stops for that item at a conflict
    and asks, as a refused edit does. The card shows "waiting to send".
11. **Two slices.** This one sets the rule by hand (item page, API, MCP). Slice 42 lets the
    classifier propose a rule behind a flag, off by default, like link proposals.
12. **Rule changes and hand-edited dates.** Each occurrence is computed from the rule, never from
    the previous due, so a monthly 31st reads Jan 31, Feb 28, Mar 31. Changing the rule keeps the
    log and starts a new streak (the item stores `rule_since`; the streak counts rows from that
    date, the strip shows all). Editing `due` by hand moves `due` only: no log row is written, the
    next tick works from the new date, and a skipped date is not logged missed. A routine cannot
    have its `due` cleared; Stop repeating first.

## The tick contract

| # | Routine | Due was | Ticked on | Done for | Logged missed | Next due |
|---|---|---|---|---|---|---|
| 1 | Daily | Mon | Mon | Mon | none | Tue |
| 2 | Daily | Mon | Wed | Wed | Mon, Tue | Thu |
| 3 | Weekly Mon + Thu | Mon | Wed | Mon, late | none | Thu |
| 4 | Weekly Mon + Thu | Mon | Fri | Thu | Mon | next Mon |
| 5 | Monthly on the 15th | Nov 15 | Nov 17 | Nov 15, late | none | Dec 15 |
| 6 | Monthly on the 15th | Nov 15 | Dec 20 | Dec 15 | Nov 15 | Jan 15 |
| 7 | Monthly on the 15th | Nov 15 | Dec 10 | Nov 15, very late | none | Dec 15 |
| 8 | Weekly Mon + Thu | Thu | Tue | Thu, early | none | next Mon |
| 9 | Monthly on the 31st | Jan 31 | Jan 31 | Jan 31 | none | Feb 28 (then Mar 31) |
| 10 | Row 1 sent twice | Mon, then Tue | Mon (retry) | nothing: `for_due` is Mon, `due` is now Tue | none | Tue |

Current streak: consecutive `done` rows back from the newest row since `rule_since`. It reads 0
once the next occurrence after `due` has passed untouched. Nothing is written for a routine nobody
ticks.

## Challenges raised

- Resetting boxes rewrites item text, so it must be atomic with the tick and must not touch
  anything but the box marker.
- "Last weekday" is ambiguous; read as "the last Friday".
- A phone mis-tap needs Undo (decision 6).
- The scope is large, so it ships in five steps, each green alone.
- Month-sized grace on monthly rules (rows 4 and 7) is intended.
- Offline ticks and text edits share one queue today (decision 10).

## Scope

**In:** everything in the decisions above.
**Out:** the classifier proposing a rule (slice 42); pause; every-N-days; yearly; notes as
routines; converting the owner's existing Routine note; a weekly view of all routines; backfill.

## Steps

Order changed after the review: a routine must not be usable before it is excluded from Today
and safe to replay. Step 1 builds one daily flow through every shared write path.

1. **Engine, migration, shared write path, exclusions.** Migration `0026` adds the rule and
   `rule_since` on items, `routine_log` and `routine_ticks`. A pure rule engine in `routines.py`
   (all five kinds, with the tick contract as tests). One tick, Undo and Stop function that the
   API, MCP `set_status`, and session `end` all call. Reminders move in `TARTIB_TZ`. Today and Pick
   exclude routines, with a guard on Pick's final write. A bare tick button on the item page for a
   daily routine, so the flow can be used end to end.
2. **Offline `ticked_on`.** Separate queue entries, ordered replay, stop at a conflict, refusal of
   a future date.
3. **Item page and row label.** Repeat control for all kinds, streaks, 30-day strip, Stop, Undo,
   the "↻" label.
4. **Home card.** Card, header count, "waiting to send".
5. **MCP surface.** `set_repeat` (null clears it); `get_item` shows the rule and streak.

## Acceptance checks

1. The ten table rows give exactly the stated done and missed rows and the next due.
2. A 31st clamps and recovers (Jan 31, Feb 28, Mar 31); the nth and last weekday are right at
   month edges, including February.
3. A tick resets boxes, moves `remind_at` to the same local time of day, and clears the pushed
   mark. Across a clock change the reminder keeps its local time; a missing local time moves to
   the next valid minute.
4. A retry, a double tap, a lost reply and a second device never tick twice.
5. Today and Pick never list a routine; Pick's final write skips a task that became a routine
   meanwhile; the card lists due, overdue and done-today ones, and counts an early tick right.
6. An offline tick made Tuesday and sent Wednesday counts for Tuesday; a future date is refused.
   Tick, edit, tick offline replays in order. A lost reply replays safely.
7. Stop repeating keeps the log. Undo restores `due`, `remind_at`, `reminded_at` and text,
   deletes every row of that tick, is refused after a later edit, and sends no duplicate push.
8. A rule change starts a new streak and keeps the log. A hand-edited `due` writes no log row.
   Clearing a routine's `due` is refused.
9. A routine nobody ticks reads streak 0 once its next occurrence passes, and writes nothing.
10. Box reset handles `[x]`, `[X]`, the markers `-`, `*`, `+`, `1.`, nesting, and leaves fenced and
    inline code alone; the same texts give the same box count in `markdown.ts` and on the server.
11. A migration on a copy of the real database leaves every existing item unchanged.

## Verification method

Unit tests for the engine from the table rows plus month edges and a clock-change case. Mutation
check of each guard (the `for_due` check, the future-date refusal, the Today exclusion, the Pick
guard, the box reset, Undo's refusal), each restored byte-identical. The migration on a copy of the
real database. `npm run ui` with screenshots of the card, the item page and an offline tick. A
live look on a phone after release. Review: a UI design pass for the card and strip (`ui.md`), and
code review before commit, by Codex on Sol in its own visible pane.

## Risks and assumptions

- The rule is one JSON text column on `items`.
- Dates in the engine are plain calendar dates; only reminder times touch time zones (decision 3).
- Rollback to `v2.9` after a routine exists leaves the extra columns and tables unused; it has not
  been tried.

## Plan review, 2026-11-09

Codex on Sol, high effort, read-only. Seven findings, all taken, none checked by a second reader.
Two were checked against the code: reminders are stored in UTC, and `reminded_at` is set once per
item (`reminders.py`).

| Finding | Where it went |
|---|---|
| A retry or second device can turn a tick into an early tick | Decision 4, `for_due`; row 10; check 4 |
| Clamp recovery, rule changes, hand-edited `due` undefined | Decision 12; row 9; check 8 |
| Undo needs a snapshot; several rows per tick | Decision 6; check 7 |
| Offline edits merge per item and cannot order ticks | Decision 10; step 2; check 6 |
| Routines usable before exclusions and safe replay | Steps reordered |
| "No daylight-saving issue" is wrong | Decision 3; check 3 |
| Missing checks: checklist syntax, streak expiry, early count, Pick guard | Checks 5, 9, 10 |
