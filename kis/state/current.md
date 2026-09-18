# Current

- Local operational detail -- the domain, how HTTPS reaches the phone, backup paths, which device
  is subscribed -- lives in `kis/state/private.md`, which is gitignored and never published. This
  file carries the substance without the specifics, and points there.

- Branch: `main`, tracking `origin/main` at `https://github.com/smkamranqadri/tartib`, public,
  working tree clean. **History is published now.** Any further rewrite is a force-push, and
  anyone who cloned in between keeps the old copy, so the three rewrites of 2026-09-18 were the
  last cheap ones. Deployed locally, not hosted anywhere yet.
  History was rewritten twice on 2026-09-18: once to one identity, `Muhammad Kamran
  <smkamranqadri@yahoo.com>` as author and committer, and once to scrub the domain, the private
  network setup and the backup paths out of blobs and commit messages both. Every SHA changed
  each time;
  the citations below are the new ones. A copy of the repository as it was before that is kept
  locally; the path is in `private.md`, and it is the undo button until the push has happened.
- Task: slice 17, deploy, step 2 of 4. Phase Mode. The image is built and proved; the push is
  blocked.
- **Blocker:** no Docker Hub credentials on this machine, so `smkamranqadri/tartib:v1.0` cannot
  be pushed. `docker login -u smkamranqadri` needs an interactive terminal, or a token through
  `--password-stdin`. Nothing else in step 2 is waiting on anything.
- Also still unconfirmed: whether the VPS is amd64. The image was built for it on that
  assumption. If it is ARM, `TARTIB_PLATFORM=linux/arm64 ./deploy.sh v1.0` is the fix and that
  build is native and quick.
  Plan and step status: `kis/intent/slice-17-deploy.md`. Slice 16 is closed.
  Plan and step status: `kis/intent/slice-16-public-repo.md`. Slice 15 is closed.
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
- One device is subscribed to push; no desktop browser has enabled reminders, so nothing is
  pushed there and a session ending only turns the bar into the outcome question on an open tab.
  Enabling it on a desktop is one switch for all three pushers and would mean two buzzes for
  every reminder and every digest. Which device, and the keys, are in `private.md`.
- Watch after deploy: the service worker returns without showing anything when a session ends
  with the app on screen. Browsers allow that only within a budget for `userVisibleOnly` pushes;
  if Chrome ever shows "This site has been updated in the background", switch that path to a
  silent notification instead of no notification.
- Run it: `docker compose up -d --build`, then http://localhost:8000. Password in `.env`.
- Verify: `cd backend && uv run pytest -q` (163 passed) and `uv run pytest -m eval` (16 real-Codex
  fixtures, needs a Codex login); `cd frontend && npm run typecheck && npm run build`.
- Reminders on a phone need HTTPS and a stable origin. How this machine provides one today, and
  how to end it, are in `private.md`. A push subscription is bound to the exact origin that
  minted it, so changing the origin means enabling reminders again afterwards.
- Push keys live in `.env`. `cd backend && uv run python -m tartib.vapid` prints a fresh set;
  regenerating invalidates every subscription, and Settings re-mints on next open.
- Not yet proved on a real device: a session ending while a *desktop tab watches the countdown*.
  That is the case migration 0008 exists for, and it should buzz either way; the retry above had
  every client closed on purpose. Nothing is pushed to a desktop browser unless that browser
  enables reminders in Settings, so what this would check is that the desktop's read no longer
  steals the phone's push.
- Next: finish step 2 by pushing `v1.0` once Docker Hub credentials exist (`./deploy.sh v1.0`),
  then step 3 -- the CapRover app: persistent dirs at `/data` and `/root/.codex`, the Codex login
  copied in, `CLAUDE_CODE_OAUTH_TOKEN` set, env from the dashboard, force HTTPS, health check,
  empty database.
  Then slice 16 (public repo) and slice 17 (harden, image, deploy, v1.0).
  Slice 17 will serve a domain (in `private.md`) from `smkamranqadri/tartib` on Docker Hub,
  tagged per version with no `latest`. DNS is live and proxied through Cloudflare, and CapRover
  already answers there with its placeholder page, so the path is wired end to end. Carried into
  slice 17: the session cookie will not be `Secure` behind that proxy until `FORWARDED_ALLOW_IPS`
  is set and Cloudflare is on Full (strict) -- proved locally, written up in the plan.
  Before slice 16 step 1, confirm `smkamranqadri@yahoo.com` is
  verified on the GitHub account, or the rewritten commits will not link to it.

## Proof

Finished slices keep their step-by-step proof in the commit messages, not here: `34ab011`,
`fc75770`, `e2e31cc`, `91d7a22`, `970348e`, and for the three most recent `6bf7f48` (the plans),
`7e7f294` (slice 12 proved on the phone, including why `failures = 0` proves nothing) and
`81ffc81` (slice 15 step 1).

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

Then applied for real, with a backup taken first (path in `private.md`), and
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

### Slice 17 step 2, 2026-09-18 — the image cross-builds and runs

`docker buildx build --platform linux/amd64` succeeds and the result is genuinely amd64, not a
manifest that merely claims to be:

```text
arch amd64 / os linux        python -c platform.machine() -> x86_64
uvicorn present, static built, codex and claude both on PATH
no stray host node_modules
booted under --platform linux/amd64: /api/health 200, index.html 200, login 200, 69MiB
```

Not pushed: this machine has no Docker Hub credentials. That is the blocker above, and it is the
only thing left in step 2.

### Slice 17 step 1, 2026-09-18 — a login that can be on the internet

Nine new tests, 163 passing, ruff clean. The backoff hangs off `auth.check_password`, so it
covers the bearer header as well as `/api/login`; a test guesses at `/api/today` to prove it, and
another proves the two doors share one counter.

Driven against the running container as well as in tests: four wrong passwords answer 401, the
fifth answers 429 with `Retry-After: 30`, and the **correct** password is refused with 429 while
blocked -- comparing it would say which guess was right. The block was cleared afterwards, and
the correct password then answered 200, so nothing is left locked.

The cookie half, which no unit test can reach because it depends on uvicorn rather than the app:
with `--forwarded-allow-ips "*"` added to the image, a login carrying `X-Forwarded-Proto: https`
now comes back `...; SameSite=lax; Secure`, and a plain http login still comes back without it,
so local development is unaffected.

The README's security section claimed there is no rate limiting. It is public now, so that was
corrected in the same commit.

### Slice 16 step 3, 2026-09-18 — published

`https://github.com/smkamranqadri/tartib`, public, `main` tracking `origin/main` at the commit
this machine has. README renders, all eight screenshots are there, GitHub's secret scanning
reports no alerts, and `kis/state/private.md` is absent from the remote -- checked by asking the
API for it, not by trusting `.gitignore`.

The pre-flight earned its place twice over. It caught the second email address still named in the
plan file that explained why that address had been removed from the commits, which would have
published in prose exactly what the rewrite took off the metadata. Fixed in the tree and scrubbed
from history before the push, as a third and final rewrite.

Three rewrites in one day, all before anything was published: one for identity, one for the
domain and the private-network setup, one for the address. That is the whole budget -- the next
one would be a force-push to a repository other people can clone.

### Slice 16 step 2, 2026-09-18 — documentation that is true

- `.env.example` now matches `config.py` in both directions; it was missing `TARTIB_DB_PATH`,
  `TARTIB_SESSION_MINUTES` and `TARTIB_STATIC_DIR`.
- README rewritten against SPEC. It had claimed three screens, listed routes that no longer
  exist, and still had pomodoro and push under "Not planned" after both shipped. Its API list
  was verified against the running app's OpenAPI rather than transcribed, its memory claim
  against `docker stats` (41.26MiB of 512MB), and its eval count corrected from 15 to 16.
- `CONTRIBUTING.md` written: how to run it, the verification commands, house style, and the
  part that matters -- rule 4 is a hard constraint, so a patch adding tags or a pomodoro history
  screen is declined on principle, and the route to changing that starts with an argument in an
  issue rather than a diff.
- Eight screenshots in `docs/screenshots/`, 1280px light and 390px dark, from a **throwaway
  database seeded with invented captures** driven through the fake classifier. Confirmed by
  query that none of that text exists in the real database, and the real one is still 32/47.
  Each screenshot was looked at, not just produced.

### Slice 16 step 1, 2026-09-18 — one identity, and no secrets

- `git filter-repo --mailmap`: 63 commits, all now `Muhammad Kamran <smkamranqadri@yahoo.com>`
  as both author and committer. Files untouched -- diffed against the pre-rewrite copy, and only
  the KIS citation edits differ.
- All eight SHAs cited in KIS were remapped through `.git/filter-repo/commit-map` and each
  resolves to a commit with the subject it had before. filter-repo also rewrote the SHAs quoted
  inside commit messages, which was not expected and is one less thing to fix.
- Full-history secret scan by hand, no scanner being installed: no PEM private key anywhere, no
  secret-shaped assignment, and the live password and both VAPID keys appear zero times. `.env`
  was never tracked.
- The plan's "move the test VAPID key into a fixture" was **void**: it was never hard-coded.
  `test_reminders.py` does `TEST_PUBLIC, TEST_PRIVATE = generate()`, a fresh pair per run. The
  claim came from a grep hit read without the line above it.
- 154 tests pass, ruff clean, typecheck and build clean after the rewrite.

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
- Reminders depend on this machine being awake and on the private network running at both ends.
  There is no hosting yet, so a closed laptop means no reminders. Slice 17 is what fixes it.