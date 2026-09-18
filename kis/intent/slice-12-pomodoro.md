# Slice 12: pomodoro (approved 2026-09-18)

A timer you start on a task, or on nothing. It logs sessions and counts today's. Allowed by
the rule 4 pomodoro carve-out of 2026-09-17, which permits session logging and forbids charts,
streaks, a history screen, and cycle or long-break logic. A session ending pushes, which needs
the third carve-out added to rule 4 on 2026-09-18.

## Config

`TARTIB_SESSION_MINUTES`, default 25. Every session is that long: no picker, no per-session
choice. A length you pick each time is a decision the timer exists to save you.

## Data

Migration 0007:

- `sessions(id, item_id NULL, started_at, ends_at, ended_at NULL, outcome NULL, created_at)`.
- `item_id` references an item and is nullable: a session can be about a task or about nothing.
  That nullable column doubles the shape of every count, and it is the price of starting a
  timer without first deciding what it is for.
- `outcome` is `done | unfinished | abandoned`, null until the sheet is answered.
- Nothing reads this table but today's counts. There is no history screen, by rule.

## The API

```text
POST   /api/sessions {item_id?}      -> 201 the session; 409 while one is running
GET    /api/sessions/current         -> the running session, or the one that just ended
                                        awaiting an outcome, or null
POST   /api/sessions/{id}/outcome {outcome}
POST   /api/sessions/{id}/stop       stop early; the same sheet follows
```

One at a time. While a session runs the UI shows it instead of a start control, so the 409 is
a guard, not a path anyone walks.

`done` also ticks the task off through `store.update_fields`, the same write path approve and
PATCH use. A session with no task cannot be `done` in that sense; it just records the outcome.

## The scheduler

One asyncio task per running session, scheduled for that session's `ends_at`, alongside the
reminder loop rather than inside it. The 60s tick is right for a reminder and wrong here: a
pomodoro that buzzes fifty seconds after the bar reached zero has told you something false.

- At startup, re-schedule every session whose `ends_at` is still ahead. A one-shot task does
  not survive a restart.
- No push if `ends_at` is more than 5 minutes past. A session that ended while the container
  was down is over; buzzing about it later is noise. Mirrors the reminder grace, shorter,
  because the useful life of "your session ended" is minutes.
- Payload `{title, url: "/", tag: "session-<id>"}`, through the same `push.broadcast`.

`sw.js` stays silent when a client is already visible: `clients.matchAll({type: "window"})`
and skip `showNotification` if any is `visibilityState === "visible"`. Being buzzed about the
countdown you are watching is the nagging rule 4 exists to prevent.

## Client

- A session bar under the capture bar on every screen while one runs: remaining time, the task
  title when there is one, and Stop. It counts down from the browser's clock against the
  server's `ends_at`; they will drift by seconds and the server is the truth.
- A start control on a task row and on the item page. Home gets one for a session with no task.
- The end sheet: **Done · Not finished · Abandoned**. It appears when the timer reaches zero,
  and on the next load after a session ended while you were away. Stopping early opens the
  same sheet.
- Today shows today's counts: the total, and per task where a session was attached.

## Briefs

The brief prompt gains a line with the space's session count for today, and `briefs.fingerprint`
gains the session count so the brief regenerates once that changes. Fingerprints are only
checked when a brief is opened, so this costs a Codex call the next time you look at a brief
for a space that had sessions, not one per session.

Only task-linked sessions have a space. A session with no task counts on Today and in no brief.

## Proof

- Backend tests through an injected clock, as slice 11 did: a session starts and a second is
  refused; a session ends and pushes once; a restart re-schedules a running session; a session
  that ended while down is not pushed; each outcome is recorded and `done` ticks the task.
- Headless Chrome against the built app: start, reload mid-session, the bar survives, the sheet
  appears after the end, each outcome, and no push while a client is visible.
- Done when: a session started on the phone ends while the app is closed, the phone buzzes
  once, and the sheet is waiting when the app is opened.

## Decided while building step 1

- Stop early is a POST, not a DELETE. Every other DELETE in this API removes a row, and a
  stopped session is kept, counted, and still owed an outcome.
- Stopping cancels the scheduled push, or the phone buzzes about a session you ended.
- Only a *running* session blocks a new one. One still owed an outcome does not.
- Ending the session is the claim to push about it: the row is closed with
  `WHERE ended_at IS NULL`, and only the call that wins that update pushes. Stopped by hand,
  tidied on a read, or already fired all fall out of the same check.
- `as_utc_iso` and `parse_iso` moved into `clock.py`, where the reminder loop's copy lived.

## Decided while building step 2

- A task you spent a session on today appears on Today, whatever its due date says. Without
  that the per-task count had nowhere to appear: a task with no due date and no star was not
  on Today at all, so the feature was invisible exactly where the plan said to show it.
- The outcome is asked inline in the same bar, not in a modal. This product has no dialogs,
  and blocking the app to ask about 25 minutes that already happened would be nagging.
- `awaiting` measures its window from when a session actually ended, not from when it was
  going to: a session stopped by hand has an `ends_at` still in the future, and asking only
  about elapsed `ends_at` made a stopped session vanish instead of asking for an outcome.

## Status
- [x] migration + API + scheduler (2026-09-18)
- [x] session bar + end sheet + Today counts (2026-09-18)
- [ ] briefs + proof + deploy
