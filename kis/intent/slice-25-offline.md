# Slice 25: offline

Planned 2026-09-21, after slice 24 closed. This is the backlog's "Offline read, and offline edit"
entry, which is the separate day slice 15 said this argument belonged on.

The app goes blank of data the moment the network does. The shell opens and a capture still
queues -- slice 15 did that part -- but every screen is empty, because the service worker returns
early for every path starting with `/api/`, so no response the app reads is ever cached. Editing
has a second cause: `offline.ts` holds one store, `pending-captures`, so an edit made offline has
nowhere to wait.

Slice 15 scoped offline *read* out in as many words, so this is deliberate rather than a
regression. It also left the principle this slice should be built on:

> The queue is not the offline path, it is the only path. Every capture is written down and then
> sent.

An offline edit gets the same shape. There is no online path and an offline path; there is one
path that copes.

## Decided with the owner, 2026-09-21

- **One slice, read and write together.** Offered as two phases the way slice 24 was, and
  declined. Recorded because it is the size risk: see Risk.
- **Network first, and the screen says how old it is.** Online nothing changes at all -- the
  network answers and you see fresh data. Offline the cache answers and the screen carries one
  muted line: *"Showing what was here 2h ago."* Not cache-first, which shows stale tasks for a
  moment even on a good connection and reshuffles the list under your eyes; not a single "you
  are offline" banner, which says the connection is down but never how old what you are reading
  is, which is the question the backlog entry actually raised.
- **Four things work offline**: tick a task done, star it, edit its text, add a thought. They are
  what you do with a note in your hand on a train, they are all small edits to one item, and they
  all replay through the endpoint the online path already uses. Everything else stays online and
  says so.
- **A queued edit shows.** It is applied over the cached data as a screen reads it, so the box
  stays ticked, and the row reads **"waiting to send"** -- slice 15's own words for a pending
  capture. Ticking a box and watching it untick is the behaviour people file bugs about.
- **Slice 24's draft hands off to the queue.** The `localStorage` draft stays what it was built
  for -- crash safety for text still being typed, inside the debounce. The moment an autosave
  actually fails, that text becomes a queued edit and the draft clears. "Still typing" and
  "typed, waiting to send" are different states and they live in different places.
- **A replayed edit refused as stale keeps slice 19's answer.** It stays queued and marked, the
  queue behind it keeps draining, and opening that item shows the strip slice 24 already built --
  Reload or Overwrite, with your words kept. No new conflict UI.

## Two traps already in the code

**`sw.js` deletes every cache that is not `CACHE` when it activates** (line 58 on 2026-09-21; line
numbers drift). A second cache for API responses is wiped on every worker activation -- and only
after an update, which is the worst way to find a bug. The keep-list becomes a set.

**`offline.ts` opens IndexedDB at version 1** and its `onupgradeneeded` creates one store. Adding
`pending-edits` means version 2 with an **additive** upgrade. Getting this wrong loses captures
that were queued on the deployed phone and never sent, which is the exact thing slice 15 built
that store to protect. It is the one irreversible change in this slice.

## The compromise, stated rather than hidden

**Counts lag.** Tick a task off offline and the row updates, but Home's tiles and a space's brief
are computed by the server. Recomputing them in the client means reimplementing the backend's
aggregation and keeping a second source of truth for it. So: **a queued edit changes item fields
wherever an item appears; aggregates lag until the queue drains**, and the stale line is what
explains the discrepancy. This was put to the owner as the one visible compromise in the slice
and accepted.

## Steps

1. **The cache.** `sw.js` keeps a second cache for `GET /api/` responses, network-first, falling
   back to the stored copy. Each entry is stamped with when it was stored. The keep-list becomes
   a set so activation stops deleting it. `SW_VERSION` is bumped -- which also pays the debt
   State records against the next deploy.
2. **The age, once.** `api()` surfaces the stamp; `useLoad` exposes it. Every screen loads
   through `useLoad`, so the line is written in one place and shown by all of them.
3. **The store.** `offline.ts` goes to DB v2 with an additive upgrade and a `pending-edits`
   store beside `pending-captures`, ordered oldest-first by the same rule -- the sort in `list()`,
   not key order.
4. **The four actions** queue when the network fails and replay through their normal endpoints.
   Anything out of scope says it needs the network rather than failing silently.
5. **The echo.** `pending.ts` applies queued edits over cached items as screens read them, and
   marks them. This is the layer the slice rests on and the one to watch for size.
6. **The hand-off.** `TextEditor`'s failed autosave enqueues and clears its draft; the readout
   becomes "waiting to send".
7. **The replay conflict.** A 409 marks that edit and leaves the rest draining; `ItemPage` shows
   slice 24's strip.

## Verification

`playwright-core` on channel chrome against the local container, the way 23 and 24 were proved.
Offline is real (`context.setOffline(true)`), not simulated by stubbing fetch.

- **R1** Offline, a **cold start in a fresh page** with the worker already installed shows Today,
  Inbox, Spaces, a space and an item with real data. This is precisely the case proved failing on
  2026-09-19; it is the check that says the slice worked.
- **R2** Each of those screens says what it is showing and how old.
- **R3** Online, nothing changes: no stale line, no stale data.
- **W1-W2** Offline: tick done, star, edit text, add a thought. Each holds and reads
  "waiting to send".
- **W3** Reconnect: all four land **once**, in the order they were made, markers clear, and the
  server holds every change.
- **W4** Offline, a start-session or an ask says it needs the network.
- **W5** A failed autosave becomes a queued edit, the `localStorage` draft clears, and the
  editor says "waiting to send".
- **C1** A replayed edit forced to 409 stays queued and marked, the rest of the queue drains,
  and the item offers Reload and Overwrite, both doing what they say.
- **X1** 390px: the stale line and the markers fit, targets clear 44px, no horizontal scroll.
- **X2** A database **seeded at v1 with pending captures** survives the upgrade to v2 with those
  captures intact. Proved against a v1 database, not a fresh one.

Then `npm run typecheck && npm run build`, and `uv run pytest -q` as a regression check -- expect
**193 passed, 2 deselected**; no backend change is planned.

## Risk

**One slice rather than two.** The echo layer sits under every screen, so building read and write
together means none of it can be judged until all of it works. The phase boundary was offered and
declined; that is the owner's call and it is recorded here rather than re-argued. If the echo
layer grows past the rest of the slice combined, that gets said out loud rather than split
silently.

**The v1 to v2 upgrade is the only irreversible thing here**, and X2 is the check that exists for
it alone.

**The worker changes, so the reload prompt is exercised for real.** `update.ts` offers "A new
version is ready" and waits for a click. Worth watching here rather than discovering it on the
deploy.

**Assumed:** every queued action is idempotent enough to replay through its normal endpoint.
Captures already are, by `client_id`. Item edits are last-write-wins per field, which is what
`expected_updated_at` is there to police.


---

## What was built, and the four things it got wrong first (2026-09-21)

**All seven steps done. 24 checks on the slice itself, green three runs running; slices 23 and 24
re-run green after it.**

`sw.js` keeps a second cache for `GET /api/`, network-first, each entry stamped with when it was
stored. `api()` reports that stamp into whatever load window is open and `useLoad` turns it into
one line, so every screen says how old it is without any screen knowing how. `offline.ts` is at
DB v2 with a `pending-edits` store; `pending.ts` lays what is queued over what was cached.

**The two traps the plan named were both real and both avoided.** The keep-list is a set, so
activation stops deleting the API cache. The v1 to v2 upgrade is additive, and X2 proves it
against a database seeded at v1 with a capture in it -- not against a fresh one.

### One decision the plan did not foresee

**The editor chunk had to be warmed.** Slice 24 deliberately kept CodeMirror out of the install
precache -- the shell should not carry 600kB for a note you only read -- and `sw.js` only caches
assets it has actually fetched. So a chunk nobody had ever needed was a chunk that was not there
when the network went, and *editing text offline was impossible*: one of the four actions chosen
for this slice could not work at all.

It is pulled down on idle now, from `TextEditor`, which mounts only on an item page. The install
still carries nothing extra and a cold item page still paints without it. **This narrows a
guarantee slice 24 made**, and its check changed with it: B2 used to assert the chunk was never
fetched on a page you only read, and now asserts it is not part of the entry the page waits on
and is fetched separately. Recorded here rather than quietly edited.

### Three things that were wrong

**A tick that would not stick, twice over.** First because the harness forced a click that the
fixed ask bar was sitting on -- `force` still dispatches at the element's coordinates, so it went
to the bar. Dispatching on the element itself fixed the test. The queue itself was right.

**`usePending()` reads IndexedDB, so it is false on the first render.** `TextEditor` set its
status once at mount, which meant reopening an item whose edit was still queued said **nothing
at all** until you typed into it. An effect syncs it now.

**Offline, nothing said a session could not start.** `getCurrentSession` fails with no network
and the session bar stays away by design, so the error had nowhere to live and the button just
did nothing. It says "You're offline." beside the button now, on the item page and in a row.

### A slice 24 bug this uncovered

**The conflict strip broke a phone.** Its message wears `.tone`, which is `nowrap` because a chip
is one or two words -- the sentence ran 430px wide and pushed a 390px screen into horizontal
scroll the moment a conflict appeared. Slice 24's phone checks never had a conflict on screen, so
nothing caught it. It wraps now.

### Verification -- what actually ran

`playwright-core` on channel chrome against the local container, offline for real
(`context.setOffline(true)`), and a second context for the writes that had to reach the server
while the first one could not see it.

| | |
|---|---|
| R1 | **a cold start in a fresh page, offline**, shows Today, Inbox, Spaces, a space and an item with real data -- the case proved failing on 2026-09-19 |
| R2 | each of those says how old what it is showing is |
| R3 | online: no stale line, no stale data |
| W1-W2 | offline: tick, star, text and a thought all hold, each reading "waiting to send" |
| W3 | on reconnect all four land **once**, the queue empties, the markers clear |
| W4 | starting a session offline says "You're offline." rather than doing nothing |
| W5 | the editor chunk is cached after one idle moment online; a failed autosave becomes a queued edit and the `localStorage` draft clears |
| C1 | a replay refused as stale shows slice 24's strip, keeps the local text, and Overwrite sends it |
| X1 | 390px offline: the stale line fits, 44px targets, no horizontal scroll |
| X2 | **a v1 database with a pending capture survives the upgrade to v2** with the capture intact |

`npm run typecheck` and `npm run build` clean. `uv run pytest -q` -- **193 passed, 2 deselected**,
unchanged; no backend was touched. Looked at: Home offline at 1280 and 390, and the queued row.

The counts-lag compromise is visible in that screenshot and behaving as agreed: the ticked row
shows struck through and "waiting to send" while the "DUE TODAY" tile still reads 3.

### Still open

Nothing in this slice. The device question is unchanged and belongs to 23 and 24.
