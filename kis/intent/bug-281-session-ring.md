# Bug #281: the session-finish ring does not play on a long-open window

Owner-scoped fix, 2026-10-07; merged into main at `192f64f` on 2026-10-09, branch and worktree
removed. The owner answered the KIS plan questions before any code: the window is **open but not
in front** when the ring fails. Push **is** enabled on that device; and the rule for the fix is
**ring only when push is off**.
Shared State belongs to the coordinator and is not changed by this stream.

## Cause (reproduced)

The ring lives in `frontend/src/session.tsx`: a `setInterval(tick, 1000)` runs while the session
state is `running`, and the ring fires only when a tick computes `left === 0`. Any
`visibilitychange`/`focus` calls `reload()`, which replaces `current` with the fresh server state
and tears the interval down.

Left open but not in front, a tab's timers are throttled and then frozen by the browser, so the
zero tick is delayed or never runs; when the window comes back, the `visibilitychange`/`focus`
reload turns the state into `awaiting` and the interval is gone before it can ring. The ring is
lost permanently. The intended announcer for that case is the server push — fine on a device with
push, silent on one without.

Repro (`probe-late.mjs`, scratch): start a real session from Home (a tap, so `unlockChime` runs),
navigate the tab away so the app is not running across the end, move the session's `ends_at` to
`now + 4s` in the database, wait past it, and return. Pre-fix build: `starts: 0`, **no ring**.
Fixed build: `starts: 1`, **rings**.

Ruled out: the visible-foreground path (a session watched in front rings correctly, proved with
`probe-ring.mjs` before and after), the `ends_at`/clock arithmetic, and `chime.ts`'s sound
selection. Not reproducible here: a genuinely hidden/occluded document — Playwright passes
`--disable-background-timer-throttling`, `--disable-backgrounding-occluded-windows` and
`--disable-renderer-backgrounding`, and even removing them, headed Chrome in this environment
reports `visibilityState: "visible"` for background tabs, minimized windows and popups. The
away-and-return repro exercises the same code path (a `reload` observing an end it did not watch).

## The fix

`session.tsx` only. The session this tab is counting (`tartib-session-tracking`) and the one it
has already rung for (`tartib-session-rung`) are kept in `sessionStorage`, so a reload or a wake
from frozen still knows what it was watching. In `reload()`, an `awaiting` session whose
`id` is the tracked one, that has not rung, and that **ran out** (`ended_at >= ends_at`, so a
session stopped by hand stays silent) rings once — unless this device has a push subscription
(`currentSubscription()` from `push.ts`), which is the announcer for that case. A push check that
throws is read as no push, so it can never cost the state update.

## Guards and mutation checks

Committed guard: `frontend/tools/ui/check.mjs`, `#281 an unwatched session end rings on return,
once, unless push is on` (stubs `/api/sessions/current`, worker blocked, fakes a subscription for
the push case). Mutations, each restored by writing the saved original back:

- drop the catch-up `void playChime()` → guard fails, "an unwatched end did not ring on return".
- `ended.ended_at >= ended.ends_at` → `true` → the held-out negative rings (standalone probe).
- `(await currentSubscription()) === null` → `true` → the push negative rings (standalone probe).

## Proof (2026-10-07)

- Repro before/after: `repro-before.log` (`starts: 0`) and `repro-after.log` (`starts: 1`).
- Rendered: `.session-bar.done` present on return; visible control still rings exactly once
  (`starts: 2` = unlock blip + one chime), so no double ring.
- Negatives: stopped by hand silent; push-faked silent.
- `npm run typecheck` clean; `npm run build` ok; `npm run ui` **24/24** (23 before this fix, plus
  the new check). Run logs are in the session scratchpad, not the repo.

## Status

Implemented on this branch, uncommitted. No backend change. Not done: a check on real hardware
for the true occluded/frozen case (this environment cannot produce it); the deploy (owner runs it).
