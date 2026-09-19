# Slice 19: small items, round two (approved 2026-09-19)

**Closed 2026-09-19; not deployed.** All six steps proved locally; the user tried the rebuilt
local container and accepted it ("good") after asking for the Inbox tabs in the title row, a
highlighted running session, and different sounds -- ending on a school bell they supplied.

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

**Done 2026-09-19.** Six eval fixtures added: four concrete dateless tasks with a due window
(follow up with the dentist, pick up the dry cleaning, reply to an email: 1-2 days; organise the
bookshelf: 1-7) and two that must stay undated ("learn to play the oud one day", "drink more
water"; task or note accepted). Run against the old prompt first: the four dated cases failed
with `due None`, the two undated passed -- the fixtures detect the change. After the prompt
change, `uv run pytest -m eval` passed 3 runs out of 3 (22 fixtures, about 30s each; the
docs' "about 3 minutes" was stale and is corrected), existing due fixtures unchanged; pytest 167
passed; ruff clean.

The classifier returns `due: null` when the text has no date, so "follow up with the dentist" is
filed undated and never reaches Today. The prompt proposes a near-term date instead: a day or
two for time-sensitive follow-ups and errands, up to a week for lower urgency, relative to now.
An explicit date always wins; notes stay undated unless a date is named.

Proof: `uv run pytest -m eval` with new fixtures for dateless tasks that should get a date *and*
ones that should stay undated; the existing due fixtures unchanged. If the stay-undated cases
fail, stop and bring it back -- Today filling with dates nobody chose is the failure to avoid.

## Step 3 — each waiting item says why

**Done 2026-09-19.** `waitingReason(item)` in `format.ts`, in order: `proposal_error` -> "AI
failed: <error>"; no proposal left -> "Proposal rejected" (a fourth cause the plan missed: reject
clears both proposal and error); no space -> "No space matched" (also covers the runner's
SpaceError path, which files with space null); otherwise "Unsure (62%)" -- an item that kept a
space and a proposal waits only because confidence was under the threshold, so the threshold is
not needed client side. The card shows it on its own line under the sentence; rows show a short
lowercase form in the meta line, without the error detail. Proof: headless Chrome at 390px, one
item of each cause (AI off, a reject, and two proposals written into a throwaway DB): the
Waiting page shows the four reasons, Home's rows show the short forms. Typecheck and build pass.

Four causes look identical on the card today. Stale tasks have their own list, so the card names
the other three, derived from fields that already exist: `proposal_error` -> "AI failed:
<error>", a proposal with no space -> "No space matched", confidence under the threshold ->
"Unsure (62%)". Wording follows rule 9.

Proof: browser, one item of each cause, each with its own line.

## Step 4 — Inbox as tabs

**Done 2026-09-19.** One `Inbox` component renders all three routes with a `tab` prop, so a tab
switch keeps what is loaded; the Waiting screen is deleted (its newest-first and Not-now order
moved in) and Recent became the tab's body. `/inbox/attention` and the old `/attention/all` go to
`/inbox`. The ask bar shows on every Inbox tab. Recent carries no count: "everything captured" is
not a number to act on, so only Needs attention and Stale show one -- a small departure from
"a count on each". Proof: headless Chrome at 390px and 1280px, with 4 waiting, 1 stale and 2
filed items: `/inbox/attention` lands on `/inbox`; the tab strip reads "Needs attention 4 · Stale
1 · Recent"; each tab shows its list at its URL; Back goes Recent -> Stale -> Needs attention;
no horizontal overflow. Typecheck and build pass. SPEC's route table and Inbox entry rewritten.

One tab strip with a count on each: Needs attention at `/inbox` (every item, not 3), Stale at
`/inbox/stale`, Recent at `/inbox/recent`. `/inbox/attention` ("Everything waiting") redirects to
`/inbox`. Back and forward move between tabs. Recent keeps slice 18's exclusion of waiting items.

Proof: browser at 390px and 1280px: tabs, counts, URLs, the redirect, Back.

Sounds, second round: the Kenney arrangements did not sound like the Pomofocus alarms the user
had in mind. Kitchen and bell are now real recordings from BigSoundBank (CC0, attribution
optional): "Mechanical alarm clock, ring #3" (2659) and "Bell #2" (2114, low-passed at 3.5 kHz).
Chosen by measuring against the user's two reference links -- spectral centroid, strike rate,
time sounding -- with the references downloaded to the scratchpad for comparison only, never
committed, and deleted after. Kitchen: 6.3 kHz / 9.9 strikes/s / 3.6 s against the reference's
6.1 / 10.4 / 3.1. Bell: 4.5 kHz / 6.4 / 2.9 s against 3.4 / 6.8 / 4.0 -- warmer than the raw
recording, still brighter than the reference. Wood is unchanged. Provenance in
`frontend/src/sounds/SOURCES.md`. Whether they are right is the user's ear.

Bell, third round: the user supplied their own pick, Pixabay's "Bel Sekolah" (153453), under the
Pixabay Content License -- use inside a project allowed, no attribution required, no
redistribution as a standalone sound. Made mono, trimmed to 3.6 s, loudness-normalised; licence
noted in `SOURCES.md`.

After a look on the device, same day: the tabs moved into the title row, right of "Inbox", in
the nav's pill style (`.pills`); under 640px they wrap to a full-width row below the subtitle.
Screenshots at 390px light and 1280px dark, no horizontal overflow.

## Step 5 — a ring when a session ends

**Done in the browser 2026-09-19; hearing it on the phone is still owed.** `chime.ts`: two sine
tones a fifth apart (880 Hz, 1318.5 Hz) with a fade, one lazily made AudioContext, unlocked by a
silent blip inside the Start tap. The session provider rings once per session, only when this
tab's countdown reaches zero -- a session stopped by hand never does, and one that ended while
the app was away is the push's. Settings > Device > Session chime, On/Off, `tartib-chime` in
localStorage, default on; choosing On plays it. Proof: headless Chrome with AudioContext stubbed
to record each tone started, a real session started from Home, its `ends_at` moved to 3s out in
the throwaway DB: switch on -> `[0, 880, 1318.5]` (the unlock blip, then the chime) and the bar
turned to "Session done"; switch off -> `[]`. The Settings switch reads On by default, stores
`off`, and stays Off after a reload. Typecheck and build pass.

The open tab plays a short chime made with Web Audio -- no sound file. A per-device switch in
Settings (localStorage), default on. The audio context is unlocked on the Start press, since iOS
plays nothing before a gesture. Rule 4 is unchanged: the session-end push is already the third
pusher, and a sound in the page is not a fourth.

Proof: browser, the chime is scheduled at session end with the switch on and not with it off;
hearing it on the phone is the user's check.

**Amended 2026-09-19, at the user's request: real alarm sounds.** The user pointed at
Pomofocus's kitchen, bell and wood alarms. Those files are Pomofocus's own and this repo is
public, so they were neither copied nor hotlinked; the user chose free-licensed recordings
instead. The three sounds are arranged from CC0 recordings in Kenney's *Impact Sounds* 1.0 --
bell strikes, wood knocks, and alternating metal and tin dings for the kitchen timer -- with
ffmpeg, about 110 KB together, provenance in `frontend/src/sounds/SOURCES.md`. (Wikimedia's
mechanical alarm clock was CC BY-SA, so not used; its CC0 door bell was not needed.) Imported
through Vite so they land in `/assets/` and the worker caches them on first fetch; the Start tap
preloads the chosen one. Settings > Device > Session sound: Bell (default, and what an old "on"
reads as), Kitchen, Wood, Off; choosing one plays it. If a file cannot be loaded, the generated
two-note chime plays instead. Proof: headless Chrome with AudioContext stubbed -- a real session
ending with each choice decodes and plays its own file (`bell-*.mp3` 44,870 bytes, `kitchen-*`
44,556, `wood-*` 20,106) and fetches nothing else, Off plays and fetches nothing; the picker
previews and stores its choice; with the service worker blocked and the MP3 aborted, the
fallback tones play. Typecheck and build pass. Whether they sound right is the user's call.

Also asked for on the device: the session bar stands out while it runs -- an accent tint and
border, the countdown and icon in the accent (`.session-bar.running`). The "done" bar is
unchanged. Seen in the same screenshots, light and dark.

## Step 6 — refuse a stale save

**Done 2026-09-19.** `expected_updated_at` on the PATCH body, excluded from the applied fields;
a mismatch is 409 "This item changed since you opened it." The item page keeps a refused edit
and offers Reload (take theirs, drop the draft) or Overwrite (send it without the check); the
editor's key now includes `updated_at`, so a reload shows the fresh values. Proof: two new tests
in `test_decisions.py` -- a stale save refused with nothing written, a fresh one taken, a toggle
without a timestamp never refused -- pytest 169 passed, ruff clean. Headless Chrome, two tabs on
one item: tab A saves; tab B's save is refused with the conflict line, its text still open and
the stored text A's; Overwrite stores B's; A's next save is refused, Reload shows B's text, and
A's save after that goes through. Also fixed here: step 2 had committed a docstring line over
ruff's 100-column limit in `test_eval.py`, edited after its lint run.

The item editor sends the `updated_at` it loaded; the PATCH returns 409 when the stored value is
newer, and the editor offers Reload or Overwrite. Row toggles (star, done) send nothing and keep
working as today, so a quick tick is never refused.

Proof: tests for 409 on stale and 200 on fresh and on no timestamp; browser, two tabs editing one
item.

## Out of scope

Backups, slices 13 and 14, the space page split view, photo and voice, and the deploy.
