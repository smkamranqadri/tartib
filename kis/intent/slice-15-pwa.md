# Slice 15: PWA — install, update, capture offline (approved 2026-09-18)

Tartib becomes the daily driver, which means it is launched from a home screen on a phone that
sometimes has no signal. Three things are missing for that. The shell is not cached until after
one successful navigation, so a fresh install can fail its first offline launch. A new worker
takes over silently, so a phone can be running code you did not knowingly ship and the only way
to tell is the hand-bumped version in Settings. And a capture typed with no network is lost.

The third reverses a line in SPEC. "Offline capture queue" has been out of scope since v0.1,
next to projects, tags and multi-user. It leaves that list here, for the same shape of reason
push and pomodoro left it: rule 4 exists so that Tartib does not nag, and a capture box that
quietly drops what you typed underground is not nagging, it is lying. Step 3 writes that
argument into SPEC beside the other two.

## Step 1 — the shell survives an install

- `install` precaches `/index.html`, both icons and the manifest, instead of waiting for a
  navigation to populate the cache. Today the first launch after an install is the one most
  likely to be offline, and it is the one that fails.
- `start_url` moves from `/today` to `/`. `/today` is a redirect kept for old links, so every
  launch currently pays a redirect to reach the route it wanted.
- The manifest gains an `id`, so a future `start_url` change does not read as a different app.
- `theme-color` follows the active theme instead of being pinned to `#111111`. The app has
  themes; the status bar should not argue with the one you picked.
- `skipWaiting()` stops being unconditional. A waiting worker surfaces one line in the shell —
  new version, reload — and takes over when the user says so. `SW_VERSION` is already shown in
  Settings and stays the way to check what a phone is running.
- `pushsubscriptionchange` is handled: re-subscribe with the stored key and re-post to
  `/api/subscriptions`. Off the backlog. Without it, a push service rotating an endpoint turns
  reminders off silently until Settings is next opened.
- iOS icon sizes and the standalone launch path checked on the phone, not only headless.

## Step 2 — a capture that is safe to send twice

`POST /api/capture` has no client-supplied identity. Replay a queued capture whose response was
never seen and you get two captures, two classifier calls, two sets of items. A queue without an
idempotency key is a duplicate generator, so the key comes first and the queue second.

Migration 0009 adds `captures.client_id`, nullable and UNIQUE. The POST accepts one; a repeat
returns the existing capture with 200 instead of creating a second with 201. Online captures
send a `client_id` too, so there is one path rather than an online one and an offline one.

`GET /api/captures/{id}` is what the app polls after every capture. It has to tolerate a capture
that has no server id yet, so the client keys a pending capture by its `client_id` until the POST
comes back with the real one.

## Step 3 — the queue

Every capture is written to an IndexedDB store first, then sent. Crash-safe online as well as
off, and it keeps the single write path the rest of this codebase has. The toast says "Saved"
when the POST lands and "Saved offline" when it did not; the row reads pending until it flushes.

Flushing happens on the `online` event, on the wake points `push.ts` already watches (mount,
`visibilitychange`, `focus`, `pageshow`), and after any successful capture. Not Background Sync:
Safari does not have it, and the phone this is for is an iPhone.

The queue flushes in insertion order and stops at the first failure, so what you typed first is
filed first.

SPEC's Out of scope line loses "offline capture queue", with the reasoning recorded there.

## Out of scope

Offline *read* of Today or Inbox — the app still needs the network to show data; that is a
separate argument on a separate day. Background Sync. Conflict resolution: captures are
append-only and `raw_text` is immutable, so there is nothing to resolve.

## Proof

- Install on the phone, airplane mode, launch: the shell opens rather than a browser error.
- Three captures typed offline; all three show pending; reconnect; all three land once, get
  classified, and no duplicates appear.
- The same `client_id` posted twice by hand: one capture, and the second call answers 200.
- Kill the app mid-flush and reopen: still no duplicates.
- Deploy a change with a tab open: it offers a reload instead of swapping underneath.
- Light theme, light status bar on the phone.
- `cd backend && uv run pytest -q && uv run ruff check .`; `cd frontend && npm run typecheck &&
  npm run build`; headless Chrome through playwright-core at 390px with the network cut over CDP.

## Files

`frontend/public/sw.js`, `manifest.webmanifest`, `frontend/index.html`, `frontend/src/main.tsx`,
`App.tsx`, `Capture.tsx`, `api.ts`, `push.ts`, `theme.tsx`, a new `frontend/src/offline.ts`,
`backend/tartib/migrations/0009_capture_client_id.sql`, `backend/tartib/captures.py`, `store.py`,
`backend/tests/test_captures.py`, `kis/intent/SPEC.md`.

Review: `/code-review` on steps 2 and 3. An idempotency key and a replay queue is exactly where
a quiet duplication bug lives.

## Status
- [ ] shell: precache, start_url, id, theme-color, update prompt, pushsubscriptionchange, iOS
- [ ] backend: migration 0009, client_id on POST /api/capture, tests
- [ ] the queue: IndexedDB, pending rows, flush on reconnect, SPEC change
