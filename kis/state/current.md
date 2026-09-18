# Current

- Branch: `main`, local only, working tree clean. Slices 11 and 12 and slice 15 step 1 are
  committed; git carries the detail. Deployed locally, not hosted anywhere yet.
- Task: none in flight. Slice 15 is closed, all three steps proved (below). Phase Mode.
  Plan and step status: `kis/intent/slice-15-pwa.md`. Slice 12 is closed.
- The worker is `2026-09-18.7` and no longer calls `skipWaiting`, so a deploy is offered as a
  reload rather than swapped in underneath. A phone on `.5` or older still has the old worker's
  behaviour until it next updates: `.5` skips the wait, so it will take `.6` on its own, once.
  After that every further update waits to be accepted. Settings shows which version is on.
  `SW_VERSION` must be bumped whenever the app changes, not only when `sw.js` does: a browser
  re-installs a worker only when its bytes differ, so a bundle-only release would otherwise leave
  the old worker active and offer no reload.
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
- Verify: `cd backend && uv run pytest -q` (154 passed) and `uv run pytest -m eval` (16 real-Codex
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
- Next: slice 16, the public repo. Step 1 is `git filter-repo` to one identity, updating the
  commit hashes KIS cites, moving the test VAPID key into a fixture, and a full-history secret
  scan. `kis/intent/slice-16-public-repo.md`. Not started.
  Then slice 16 (public repo) and slice 17 (harden, image, deploy, v1.0).
  Slice 17 will serve `https://the domain` from `smkamranqadri/tartib` on Docker
  Hub, tagged per version with no `latest`. DNS is live and proxied through Cloudflare, and
  CapRover already answers there with its placeholder page, so the path is wired end to end.
  Carried into slice 17: the session cookie will not be `Secure` behind that proxy until
  `FORWARDED_ALLOW_IPS` is set and Cloudflare is on Full (strict) -- proved locally, written up
  in the plan. Before slice 16 step 1, confirm `smkamranqadri@yahoo.com` is
  verified on the GitHub account, or the rewritten commits will not link to it.

## Proof

Finished slices keep their step-by-step proof in the commit messages, not here: `ecd2000`,
`8a897ad`, `7d8ffd6`, `6c5c16b`, `9a80a28`, and for the three most recent `1923c7c` (the plans),
`70e91c6` (slice 12 proved on the phone, including why `failures = 0` proves nothing) and
`6d78953` (slice 15 step 1).

Still operational from that: session 2 is owed an outcome, so the Done / Not finished /
Abandoned question is sitting in the bar until it is answered.

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

### Slice 15 step 2, 2026-09-18 — a capture that is safe to send twice

Migration 0009 adds `captures.client_id` and a unique index over it. Run first against a copy of
the live database: 32 captures and 47 items before and after, schema 8 to 9, and all 32 NULLs
sitting under the unique index without complaint, which is the whole reason a unique index was
used rather than a constraint.

Then applied for real (`a local backup` is the backup taken first) and
driven through the running app with one `client_id` sent three times:

```text
attempt 1 -> HTTP 201  {"id":33}
attempt 2 -> HTTP 200  {"id":33}
attempt 3 -> HTTP 200  {"id":33}
one row in captures, not three
```

That test capture and the item it produced were deleted afterwards; the database is back to 32
and 47. 154 backend tests pass, ruff clean. Four migration tests pin the schema version and were
bumped from 8 to 9, as every migration before this one has had to do.

### Slice 15 step 3, 2026-09-18 — the queue

Headless Chrome at 390px against a throwaway instance on port 8001 with its own database, so
none of this touched the real one (still 32 captures, 47 items):

```text
PASS  offline capture says so                     "Saved offline"
PASS  three captures are waiting                  3 rows
PASS  they are in IndexedDB, and sort oldest first
PASS  the queue survives a reload while offline   3 rows
PASS  offline says you're offline                 "You're offline."
PASS  nothing is left waiting / it says what it sent  "Sent 3 captures"
PASS  all three arrived, oldest first, no duplicates
PASS  a second flush sends nothing
```

The run before that one failed three ways and one was a real bug: pending rows were inside
`{data && ...}` and `data` is null exactly when offline, so the queue worked and could not be
seen. Screenshot of the fixed offline state confirmed by eye, not just by selector count.

154 backend tests pass, ruff clean, typecheck and build clean.

## Known gaps

- The Claude fallback inside Docker needs `CLAUDE_CODE_OAUTH_TOKEN` from `claude setup-token`; without it a Codex outage still parks captures in the Inbox.
- Voice capture depends on the browser; it was proved with an injected engine, not real dictation.
- The digest counts `stage='attention'` only, so it does not include the 14-day stale tasks the
  Inbox screen also shows.
- `pushsubscriptionchange` is handled since slice 15 step 1, but unproved: it needs a push
  service to actually retire an endpoint, and Safari never fires the event, so on the phone a
  rotation still means reminders are silently off until Settings is next opened.
- Tapping a reminder on iOS opens Tartib but does not navigate to `/today`. Whether iOS runs the
  worker's `notificationclick` at all was never established; `technical.md` records what was tried.
- Reminders depend on the Mac being awake and on a private network running at both ends. There is no
  hosting, so a closed laptop means no reminders.