# Slice 19: small items, round two (approved 2026-09-19)

Six independent steps from the backlog, each proved on its own. No deploy in this slice.

Settled while planning, from the code rather than the backlog: "a notification key that cannot
fire twice" was already true -- reminders hold `reminded_at`, the digest holds `digest_date` in
state, and the session-end push claims `notified_at` with a conditional UPDATE (migration 0008)
-- so it was dropped. "One set of shared rules across both prompts" moved under slice 14: today
the prompts share about three lines, and the header format exists only in ask; the refactor pays
when classify gains item context.

## Step 1 — a failed capture is retried

**Done 2026-09-19.** "Touched" is judged by content, not timestamps: the one item must still be
exactly what the fallback wrote. `classified_at` has second precision and the touch trigger
stamps milliseconds, so comparing them would misjudge; the content check also covers failures
from before migration 0010. The count is of retries: the original attempt plus at most 3.
Proof: new `tests/test_retry.py`, 8 tests -- a success sends a failed capture again (fallback
note replaced, `attempts` 1), the probe finds one with no new capture, one that always fails
stops at 3, an item starred, retitled, reshaped or given a space is left alone, and AI-off is
never picked -- passing 5 runs out of 5; the migration-count asserts moved from 9 to 10. Full
suite 167 passed, ruff clean.

A capture that failed (`status = 'error'`, one fallback item in attention with
`proposal_error`) waits for a human today, or for `python -m tartib.reclassify --attention`.
With Codex the only classifier since slice 18, every outage parks captures.

- Retry on a probe every 15 minutes, and in a pass straight after any capture classifies
  successfully (proof Codex is back).
- At most 3 attempts per capture, counted in `captures.attempts` (migration 0010).
- Skip `AI not configured`, and any capture whose fallback item the user has touched -- edited
  since it was created, or filed.
- A retry removes the untouched fallback item and runs the capture as new, reusing the reset in
  `reclassify.py`. The runner acts only on `pending` rows, so a retry cannot double-file.

Proof: tests for the probe, the after-success pass, the cap, and the touched-item skip.

## Step 2 — an undated task gets a proposed date

The classifier returns `due: null` when the text has no date, so "follow up with the dentist" is
filed undated and never reaches Today. The prompt proposes a near-term date instead: a day or
two for time-sensitive follow-ups and errands, up to a week for lower urgency, relative to now.
An explicit date always wins; notes stay undated unless a date is named.

Proof: `uv run pytest -m eval` with new fixtures for dateless tasks that should get a date *and*
ones that should stay undated; the existing due fixtures unchanged. If the stay-undated cases
fail, stop and bring it back -- Today filling with dates nobody chose is the failure to avoid.

## Step 3 — each waiting item says why

Four causes look identical on the card today. Stale tasks have their own list, so the card names
the other three, derived from fields that already exist: `proposal_error` -> "AI failed:
<error>", a proposal with no space -> "No space matched", confidence under the threshold ->
"Unsure (62%)". Wording follows rule 9.

Proof: browser, one item of each cause, each with its own line.

## Step 4 — Inbox as tabs

One tab strip with a count on each: Needs attention at `/inbox` (every item, not 3), Stale at
`/inbox/stale`, Recent at `/inbox/recent`. `/inbox/attention` ("Everything waiting") redirects to
`/inbox`. Back and forward move between tabs. Recent keeps slice 18's exclusion of waiting items.

Proof: browser at 390px and 1280px: tabs, counts, URLs, the redirect, Back.

## Step 5 — a ring when a session ends

The open tab plays a short chime made with Web Audio -- no sound file. A per-device switch in
Settings (localStorage), default on. The audio context is unlocked on the Start press, since iOS
plays nothing before a gesture. Rule 4 is unchanged: the session-end push is already the third
pusher, and a sound in the page is not a fourth.

Proof: browser, the chime is scheduled at session end with the switch on and not with it off;
hearing it on the phone is the user's check.

## Step 6 — refuse a stale save

The item editor sends the `updated_at` it loaded; the PATCH returns 409 when the stored value is
newer, and the editor offers Reload or Overwrite. Row toggles (star, done) send nothing and keep
working as today, so a quick tick is never refused.

Proof: tests for 409 on stale and 200 on fresh and on no timestamp; browser, two tabs editing one
item.

## Out of scope

Backups, slices 13 and 14, the space page split view, photo and voice, and the deploy.
