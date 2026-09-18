# Current

- Branch: `main`, local only, working tree clean. Slice 11 is committed (three commits,
  `ecd2000`, `c38495b`, `8a897ad`) and deployed.
- Task: slice 12, pomodoro. Step 1 of 3 done; step 2 (session bar, end sheet, Today counts) is
  next. Phase Mode.
  Plan and step status: `kis/intent/slice-12-pomodoro.md`.
- Verification plan for step 2: `npm run typecheck && npm run build`, then the built app in
  headless Chrome: start, reload mid-session, the bar survives, the sheet after the end, each
  outcome, and no push while a client is visible.
- The session push has no visible-client suppression yet: `sw.js` gets it in step 2, so until
  then a session ending buzzes even with the app open.
- Decided while starting step 1, where the plan was silent:
  - Stop early is `POST /api/sessions/{id}/stop`, not `DELETE`. Every other DELETE in this API
    removes a row, and a stopped session is kept, counted, and given an outcome.
  - Stopping cancels the scheduled push. Otherwise the phone buzzes about a session you ended.
  - Only a *running* session blocks a new one. A finished session still waiting for its outcome
    must not stop you starting the next.
  - A session waiting for an outcome follows you for 12 hours, then stops being offered. An
    outcome sheet for something from two days ago is an ambush, not a question.
- Run it: `docker compose up -d --build`, then http://localhost:8000. Password in `.env`.
- Verify: `cd backend && uv run pytest -q` (144 passed) and `uv run pytest -m eval` (16 real-Codex
  fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Reminders on the phone: HTTPS comes from the private network's HTTPS, so they keep working for as long as
  that network runs on the Mac and the phone, and the Mac is awake. Nothing is exposed publicly.
  `the serve command` and `the network down command` end it; doing so means enabling
  reminders again afterwards, since a subscription is bound to that exact origin.
- Push keys live in `.env` (2026-09-18). `cd backend && uv run python -m tartib.vapid` prints a
  fresh set; regenerating invalidates every subscription, and Settings re-mints on next open.
- Settings shows the installed service worker version (`DEVICE` -> Reminders worker). A phone
  silently sitting on an old worker cost a whole debugging round before that existed.
- Backups from the deploy: `a local backup directory/` holds the pre-deploy database and `.env`.
- Next: slice 12, step 2 of 3: the session bar under the capture bar, the start control on a task
  row and item page, the Done / Not finished / Abandoned sheet, today's counts on Today, and the
  visible-client check in `sw.js`.

## Proof (2026-09-18) — slice 12 step 1

- `uv run pytest -q` - 144 passed (was 127); ruff check and format clean. The four decisions
  above are mutation-checked: removing the 409, the push grace, the task tick, or the 12-hour
  window each fails a named test.
- Migration rehearsed on a copy of the live database: 6 -> 7 clean, 47 items intact.
- In a container built from this tree, with a one-minute session: a second start was refused,
  the container ended the session by itself at the minute with nobody polling it, the outcome
  was recorded, and Today counted it. A session planted to end after a restart was still
  running afterwards and pushed at its own end, which is the scheduler being rebuilt on boot.
- Not proved yet: anything visible. There is no UI until step 2.

## Review after the slice 11 work (2026-09-18)

A review of the committed slice found two real defects, both fixed and mutation-checked:

- One tick sends one notification per due item, and each failure was counted separately, so a
  handful of reminders during a single outage spent all eight strikes and deleted a live
  subscription. A tick now charges one strike per endpoint.
- An unusable VAPID key left the loop off but still advertised `vapid_public`, so Settings would
  offer to enable reminders, say "on", and never deliver one.

Also: the wake-up retries in `App.tsx` restarted on every route change (`useNavigate` changes
identity), so moving around the app kept a 500ms poll alive; taking the pending note was not
guarded against two readers, which could push the same route twice; and the worker version row
said "not installed" for exactly the stale worker it was built to catch.

## Proof (2026-09-18) — slice 11 step 3, on the phone

Deployed to the live container: schema 6, all 47 items intact, public key served and the private
key absent from every response. Real Apple Web Push subscription from the phone
(`web.push.apple.com`), made through Settings over HTTPS.

Three reminders armed two minutes out, each fired by the 60s loop within 36 to 48 seconds of
coming due, each accepted by Apple with the subscription's failure count staying at 0. The phone
buzzed on a locked screen.

Tapping the notification does not open `/today`: the app opens wherever it was left. Three
approaches were tried and each was confirmed installed on the phone before being ruled out; the
plan records them. Accepted as a limitation rather than fixed.

An automated browser cannot substitute for the phone here: Playwright's Chrome has no
push-service credentials, so `pushManager.subscribe()` fails with "Registration failed -
permission denied" both headless and headed.

## Proof (2026-09-18) — slice 11 step 2

The built app driven in headless Chrome, because the service worker only registers in a
production build:

- 20 checks on Settings: the worker registers, the button appears only before asking, enabling
  POSTs with the server's own key and flips the card to "on", turning off drops the row, and the
  blocked and no-key states each explain themselves and offer no button that cannot work.
- A push delivered to the real service worker shows the reminder carrying `/today`. Tapping it
  (the handler fired in the worker's own scope) takes the open tab there by routing in the app:
  a half-typed capture survived, and a tap while already on `/today` reloads nothing.
- Two reminders due in one tick both survive; the same reminder re-fired still replaces itself.
- Rotating the server's VAPID key: the stale subscription is dropped, re-minted with the new key,
  and the dead row deleted, ending at exactly one subscription.
- The failure counter, in the real container against an unresolvable push host: the subscription
  survives seven failed pushes and is dropped on the eighth. Migration 0006 rehearsed on a copy
  of the live database, 4 -> 6 clean.
- Screenshots at 390px and 1280px, in light and dark, plus the failed-enable error state.
- Not proved here: a real push service (Chrome's is unreachable, so `PushManager.subscribe` is
  stubbed; everything on our side of it is real) and a real phone. Both are step 3.

## Proof (2026-09-17) — slice 11 step 1:

- `cd backend && uv run pytest -q` - 121 passed (was 92); `uv run ruff check .` and
  `ruff format --check .` - clean. Three times in a row, and under three machine timezones.
- The new guards were mutation-checked: breaking the trigger, the re-arm rule, the stage filter,
  the digest seed, or the key check each fails a named test.
- Migration rehearsed on a copy of the live 47-item database: 4 -> 5 clean, a past reminder
  written off, a future one still armed, no item's `updated_at` moved.
- In a container built from this tree, on a spare port: a reminder armed one minute back fired on
  the loop's own 60s tick with nobody poking it, the push reached real DNS, the failure was logged
  and the subscription kept (only 404/410 deletes one), and the private key appears in no log line.
  A truncated key logs "reminders stay off" and the app still serves.
- Not proved yet: anything on a phone, and any real push accepted by a real push service.

Earlier (v0.1): every route driven headlessly at 390px and 1280px with the fake classifier; real
Codex exercised on the host for classification, briefs, and ask.

## Known gaps

- The Claude fallback inside Docker needs `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`; without it a Codex outage still parks captures in the Inbox.
- A brief refreshes only when an item is added or removed, or on its refresh icon.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox screen also shows.
- No `pushsubscriptionchange` handler: when a push service rotates an endpoint, reminders are
  silently off until the user next opens Settings, which re-registers it.
- Tapping a reminder on iOS opens Tartib but does not navigate to `/today`. Whether iOS runs the
  worker's `notificationclick` at all was never established; see the plan for what was tried.
- Reminders depend on the Mac being awake and on a private network running at both ends. There is no
  hosting, so a closed laptop means no reminders.
