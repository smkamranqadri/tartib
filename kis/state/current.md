# Current

- Branch: `main`, local only, working tree clean. Slices 11 and 12 are committed and deployed;
  git carries the detail.
- Task: slice 12, pomodoro, step 3 of 3. Deployed and proved on the live app; the last check
  needs the phone. Phase Mode.
  Plan and step status: `kis/intent/slice-12-pomodoro.md`.
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
- Next: the one thing left on slice 12. Start a session on the phone, close the app, and check it
  buzzes once when the time is up. `TARTIB_SESSION_MINUTES` is 25 in `.env`; set it to 1 and
  `docker compose up -d` if you would rather not wait, then put it back.

## Proof (2026-09-18) — slice 12 on real devices

A 25-minute session started from the phone on a real task appeared on the desktop with the same
countdown, which is the whole point of the session being a row rather than a tab. It ended at its
scheduled second, 07:48:32Z.

No push went out for it, and the failure counter staying at 0 was mistaken for proof that one
had: it only shows nothing failed. The desktop watching the countdown asked the server the moment
it hit zero, that read closed the session, and the push had no claim left. Fixed by migration
0008; the phone buzz is still unproved, and the first retry should be with every other client
closed.

Step-by-step proof for slices 11 and 12 is in the commit messages, not here: `ecd2000`,
`8a897ad`, `7d8ffd6`, `6c5c16b`, `9a80a28`.

Earlier (v0.1): every route driven headlessly at 390px and 1280px with the fake classifier; real
Codex exercised on the host for classification, briefs, and ask.

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