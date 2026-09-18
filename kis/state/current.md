# Current

- Branch: `main`, local only, working tree clean. Slices 11 and 12 are committed and deployed;
  git carries the detail.
- Task: slice 15, PWA, step 1 of 3 done and proved (below). Phase Mode.
  Plan and step status: `kis/intent/slice-15-pwa.md`. Slice 12 is closed.
- The worker is `2026-09-18.6` and no longer calls `skipWaiting`, so a deploy is offered as a
  reload rather than swapped in underneath. A phone on `.5` or older still has the old worker's
  behaviour until it next updates: `.5` skips the wait, so it will take `.6` on its own, once.
  After that every further update waits to be accepted. Settings shows which version is on.
- Approved and planned next, in order: slice 15 PWA (`kis/intent/slice-15-pwa.md`), slice 16
  public repo (`kis/intent/slice-16-public-repo.md`), slice 17 deploy
  (`kis/intent/slice-17-deploy.md`). Remote exists and is empty:
  `https://github.com/smkamranqadri/tartib.git`, public.
- Only the phone is subscribed to push (`web.push.apple.com`, one row). No desktop browser has
  enabled reminders, so nothing is pushed there: a session ending only turns the bar into the
  outcome question on an open tab. Enabling it on a desktop is one switch for all three pushers
  and would mean two buzzes for every reminder and every digest.
- Watch after deploy: the service worker returns without showing anything when a session ends
  with the app on screen. Browsers allow that only within a budget for `userVisibleOnly` pushes;
  if Chrome ever shows "This site has been updated in the background", switch that path to a
  silent notification instead of no notification.
- Run it: `docker compose up -d --build`, then http://localhost:8000. Password in `.env`.
- Verify: `cd backend && uv run pytest -q` (149 passed) and `uv run pytest -m eval` (16 real-Codex
  fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Reminders on the phone: HTTPS comes from the private network's HTTPS, so they keep working for as long as
  that network runs on the Mac and the phone, and the Mac is awake. Nothing is exposed publicly.
  `the serve command` and `the network down command` end it; doing so means enabling
  reminders again afterwards, since a subscription is bound to that exact origin.
- Push keys live in `.env` (2026-09-18). `cd backend && uv run python -m tartib.vapid` prints a
  fresh set; regenerating invalidates every subscription, and Settings re-mints on next open.
- Backups from the deploy: `a local backup directory/` holds the pre-deploy database and `.env`.
- Not yet proved on a real device: a session ending while a *desktop tab watches the countdown*.
  That is the case migration 0008 exists for, and it should buzz either way; the retry above had
  every client closed on purpose. Nothing is pushed to a desktop browser unless that browser
  enables reminders in Settings, so what this would check is that the desktop's read no longer
  steals the phone's push.
- Next: slice 15 step 2 -- migration 0009, `captures.client_id` UNIQUE, and a POST that returns
  the existing capture instead of making a second. Not started.
  Then slice 16 (public repo) and slice 17 (harden, image, deploy, v1.0).
  Two values still needed, neither blocking slice 15: the Docker Hub namespace for the image and
  the domain CapRover will serve. Before slice 16 step 1, confirm `smkamranqadri@yahoo.com` is
  verified on the GitHub account, or the rewritten commits will not link to it.

## Proof (2026-09-18) — slice 12 on real devices

A 25-minute session started from the phone on a real task appeared on the desktop with the same
countdown, which is the whole point of the session being a row rather than a tab. It ended at its
scheduled second, 07:48:32Z.

No push went out for it, and the failure counter staying at 0 was mistaken for proof that one
had: it only shows nothing failed. The desktop watching the countdown asked the server the moment
it hit zero, that read closed the session, and the push had no claim left. Fixed by migration
0008; the phone buzz is still unproved, and the first retry should be with every other client
closed.

### Retry 2026-09-18 08:36Z — the server half, proved

Session 2, one minute, no task, started through the API with no browser tab open anywhere.
At 08:36:53Z, its own `ends_at` to the second:

- `notified_at = 2026-09-18T08:36:53Z`. This is the thing that was NULL last time. The claim is
  now held separately from `ended_at`, so closing the row no longer takes the notification with
  it. Migration 0008 does what it was written to do.
- `push.broadcast` ran and `send` did not raise. `pywebpush` raises `WebPushException` on any
  non-2xx, `broadcast` turns that into a strike, and `subscriptions.failures` is still 0 with no
  warning in the log. So Apple's push service accepted the notification.
- Note for next time: `failures = 0` alone still proves nothing, and `last_seen_at` is not
  evidence either — `mark_delivered` only clears a non-zero count and never touches it. What
  makes this proof is `notified_at` being claimed *and* no strike recorded.

The phone buzzed once, confirmed by the user. `GET /api/sessions/current` then returned
`state: "awaiting"` for session 2, which is what the session bar renders as the Done / Not
finished / Abandoned question -- the third part of the criterion.

Seam, recorded rather than papered over: no single run covered every word of "a session started
on the phone ends while the app is closed". Session 1 was started on the phone; session 2 was
started through `POST /api/sessions`, which is the identical endpoint the phone's Start button
calls, and ended with no client anywhere. Each half is proved and there is no third code path
between them. Session 2 is still owed an outcome, so the question is sitting in the bar.

Step-by-step proof for slices 11 and 12 is in the commit messages, not here: `ecd2000`,
`8a897ad`, `7d8ffd6`, `6c5c16b`, `9a80a28`.

Earlier (v0.1): every route driven headlessly at 390px and 1280px with the fake classifier; real
Codex exercised on the host for classification, briefs, and ask.

### Slice 15 step 1, 2026-09-18 — the shell

Headless Chrome through playwright-core at 390px, against the rebuilt container on
localhost:8000, signed in as the real app:

- The shell cache after install holds `/index.html`, both hashed assets, all three icons, the
  manifest and the version marker. The assets are the point: `index.html` only names them, and
  caching the HTML without them is a blank page with a title.
- Offline reload renders the whole app -- header, nav, capture bar, page chrome. Offline deep
  link to `/spaces` renders it too.
- `theme-color` reads `#0f1412` on dark and `#f2f5f3` on light, both metas, after a reload.
- `start_url` is `/` and the manifest has an `id`.
- Update handover, with a new worker published into the container mid-session: nothing is
  offered on a current install; the new worker is offered and not forced; the old one stays in
  charge until the button is pressed; pressing it hands over and the app still works.

`cd backend && uv run pytest -q` 149 passed, `uv run ruff check .` clean, `npm run typecheck`
and `npm run build` clean. Backend untouched this step; those ran as an integration check.

Not proved: `pushsubscriptionchange`. See the plan's "Found while building step 1".

## Known gaps

- The Claude fallback inside Docker needs `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`; without it a Codex outage still parks captures in the Inbox.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox screen also shows.
- No `pushsubscriptionchange` handler: when a push service rotates an endpoint, reminders are
  silently off until the user next opens Settings, which re-registers it.
- Tapping a reminder on iOS opens Tartib but does not navigate to `/today`. Whether iOS runs the
  worker's `notificationclick` at all was never established; `technical.md` records what was tried.
- Reminders depend on the Mac being awake and on a private network running at both ends. There is no
  hosting, so a closed laptop means no reminders.