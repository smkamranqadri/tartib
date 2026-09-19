# Slice 18: small fixes (approved 2026-09-19)

**Status 2026-09-19: all six steps done and proved locally; not deployed.** Owed before the slice
counts as closed: on the phone, that tapping the capture box no longer zooms (step 5) and that
the installed app's header clears the notch and scrolls smoothly (step 6). Both need `v1.1` on
the server, or the local container reached from the phone.

Picked for being small: the cause is known, one or two files each, no migration, no prompt
change. Six independent steps, each proved on its own. No deploy in this slice -- it ends green
locally, and `v1.1` ships when asked for.

## Step 1 — Codex is the only classifier

**Done 2026-09-19.** pytest 158 passed (163 less the 5 fallback tests); ruff clean; frontend
typecheck and build pass; `git grep -i "claude\|ai_fallback"` outside KIS and agent config finds
only `.dockerignore`; `docker build` succeeds, `command -v claude` in the image finds nothing,
`codex --version` is 0.153.2, image 1.07GB locally (arm64, so not comparable with the backlog's
1.62GB). README's fallback sentence now points at `python -m tartib.reclassify --attention`, the
existing way to rerun parked captures -- there is no retry in the UI.

The Claude fallback goes, all of it. Decided 2026-09-19 instead of fixing the hang: it has never
run on the deployed host (State, Open), and while it is configured a Codex failure costs 120s and
fails anyway. Rule 3 becomes Codex-only when this step lands.

- `backend/tartib/codex.py`: `_run_claude`, `_claude_args`, `dialect`, the runner table and the
  fallback leg. `config.py`: `ai_fallback_command`, `ai_fallback_model`.
- The `"fallback"` key leaves `/api/health` (`main.py`) and `/api/config` (`queries.py`); the
  "Claude fallback" row leaves Settings and the field leaves `api.ts`.
- Tests: `test_fallback.py` and `fake_claude.py` deleted, `FAKE_CLAUDE*` out of `conftest.py`,
  the `fallback` assertions in `test_auth.py` and `test_queries.py` updated.
- `Dockerfile` stops installing `@anthropic-ai/claude-code`. `.env.example`, `README.md` and
  `docs/deploying.md` lose every fallback line.

Proof: pytest green; `git grep -i "claude\|ai_fallback"` outside `kis/` and agent config finds
nothing but `.dockerignore`; the image builds and `claude` is not on its path.

Consequence, accepted: a Codex outage parks every capture in Needs Attention with
`proposal_error`. It did that already, 120s slower. Automatic retry of those items stays a
backlog candidate and matters more now.

## Step 2 — Settings says why it is stuck

**Done 2026-09-19.** Headless Chrome at 390px against a throwaway server, `/api/config` aborted:
the page shows "Can't reach Tartib." with Retry, and the Reminders row reads "Can't tell until
this install's settings load." instead of "Checking...". Unblocked, Retry removes the error and
the page resolves (timezone `UTC`, push "no push key set up", correct for that server).
Typecheck passes.

`Settings.tsx:24` keeps only `.data` from `useLoad`. Show its `error` with `ErrorLine` and a
Retry that reloads the config.

Proof: in a browser with `/api/config` blocked, the page shows the error and Retry instead of
"..."; unblocked, Retry resolves the page.

## Step 3 — Recent does not repeat Needs Attention

**Done 2026-09-19.** New test `test_recent_page_leaves_out_what_is_waiting` (a mixed capture lists
only its filed item, an all-attention capture is absent until approved, Today's three unchanged)
fails on the old query and passes on the new; pytest 159 passed. Headless Chrome at 390px, one
filed and one waiting capture: the Inbox Recent card and `/inbox/recent` show only the filed one,
Needs Attention shows the waiting one, Home's Recent shows both.
`test_a_queued_capture_is_safe_to_send_twice` counted rows through `/api/recent` with AI off, so
its capture is now hidden there; it counts through `/api/today` instead. The Inbox card can show
fewer than three while its header still says "last 3" -- left as is.

Applies to the `/inbox/recent` page (server side, `/api/recent` in `queries.py`) and the Inbox
Recent card (which reads `/api/today`, shared with Home, so filter it in `Inbox.tsx`). Home's
Recent card is unchanged: Needs Attention is not on that screen, and a capture you just typed
should not vanish from it.

The rule: a capture drops its `stage='attention'` items; a capture whose items are *all* in
attention is not listed; a capture with no items yet (still classifying) stays. On the server the
exclusion is in the SQL, so keyset pages stay full.

Proof: a test that a capture parked in attention is absent from `/api/recent` and a mixed one
lists only its filed item; the Inbox card checked in a browser.

## Step 4 — a new space reaches the pickers

**Done 2026-09-19.** Reproduced in headless Chrome at 1280px before fixing, two ways. Created on
Spaces and reached through the nav, the Inbox picker had it but the ask bar did not (`App.tsx`
loaded it once per login). Created by another client with the Inbox open, neither had it, even
after the tab regained focus -- the likely shape of the report, a phone left open. Fix: one
`useSpaces(version)` hook for every picker (App's ask bar, Inbox, Waiting, ItemPage) that reloads
on `version` and when the page becomes visible again; only the names reload on return, never the
screen's data, so an open edit is not disturbed. After: both cases show the new space. Typecheck
and build pass. Not covered, on purpose: a screen that stays in the foreground the whole time
does not poll.

Reported, not reproduced. Inbox and Waiting both refetch spaces on mount, so the backlog's guess
may not be the path. Reproduce first and fix what reproduces. Fixed regardless: the ask bar's
list, which `App.tsx:139` loads once per login -- it reloads on `version` like everything else.

Proof: a space created on Spaces appears in the Inbox picker and the ask bar with no reload.

## Step 5 — no zoom on focus

**Done in the browser 2026-09-19; the phone check is still owed.** One rule beside the existing
`font: inherit` puts `input, textarea, select` at 16px; the capture box's 15px and the two hand-set
16px overrides are gone. Headless Chrome at 390px (mobile, touch) read the computed size of every
field on nine screens -- Home, Inbox, Waiting, Recent, Spaces with the new-space form open, a
space, two item pages, Settings: 23 fields, all 16px. Screenshot of Home shows no layout change
beyond the larger field text. Whether Mobile Safari stops zooming can only be seen on the phone.

One global rule puts every `input`, `textarea` and `select` at 16px; the two hand-set 16px
overrides and the capture box's explicit 15px go.

Proof: computed font-size 16px on every field at 390px; on the phone, tapping the capture box
does not zoom (the user checks).

## Step 6 — a sticky glass nav, clear of the notch

**Done in the browser 2026-09-19; the phone check is still owed.** `.top` is `position: sticky`
with the page background at 78% and a 14px blur, bleeding into the gutters; the gutters became a
`--gutter` variable floored at `env(safe-area-inset-left/right)`, and the nav's top padding adds
`env(safe-area-inset-top)`. Headless Chrome, scrolled 500px on `/inbox/recent` with 16 seeded
captures: the nav stays at y=0 at 390px light and dark and at 1280px dark, content blurs under
it, and the document is never wider than the viewport. With insets emulated through CDP
(`Emulation.setSafeAreaInsetsOverride`, top 47, bottom 34) the nav's top padding grows from 14px
to 61px and the brand sits below the notch line. Typecheck passes; pytest 159 passed. Scroll
smoothness with two blurred layers, and the real notch, can only be judged on the phone.

The top bar (`.top`) sticks while the page scrolls, translucent with a blur -- the ask bar's
treatment. This replaces the backlog's "opaque menus": the menus were already opaque, and the
2026-09-19 decision was for glass, on the nav. Safe-area insets added at the top and sides.

Proof: at 390px the nav stays pinned and content blurs under it; on the phone, installed, the
header clears the notch (the user checks). Watch for scroll jank with two blurred layers.

## After the first phone look, 2026-09-19

Asked for on the device: the nav more transparent, and every menu drawn like the iOS space picker
in a proposal (a native `<select>`, so iOS's own glass). One `--glass-blur` token (`blur(20px)
saturate(180%)`) now drives the nav (page background at 55%, was 78%), the ask bar (panel at 60%,
was 82%, with its field and select at 70%) and the `...` menus (panel at 62%, previously solid).
Screenshots at 390px, light and dark, show the Inbox card menu over the next card, the nav and the
ask bar with content blurred through, text readable. The phone checks above now include these.

## Out of scope

Backups, slices 13 and 14, the due-date prompt, the notification key, the rest of UI polish
(skeletons, fonts), automatic retry for `proposal_error`, and the deploy.
