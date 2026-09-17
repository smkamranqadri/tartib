# Slice 11: push reminders (approved 2026-09-17)

Web Push for reminders the user set, plus one daily digest. Allowed by the rule 4 carve-out
of 2026-09-17. Nothing else pushes.

## Keys and config

`TARTIB_VAPID_PUBLIC`, `TARTIB_VAPID_PRIVATE`, `TARTIB_VAPID_EMAIL`, `TARTIB_SUMMARY_TIME`
(default `08:00`, read in `TARTIB_TZ`). Signing is `pywebpush`; it pulls `cryptography`, and
that image cost is accepted here rather than discovered later.

`GET /api/config` gains the **public** key only. The private key never appears in a response,
a log line, or an error body.

## Data

Migration 0005:

- `items.reminded_at TEXT` (UTC ISO, null = not yet sent).
- `subscriptions(id, endpoint UNIQUE, p256dh, auth, created_at, last_seen_at)`.
- Backfill: every existing row with `remind_at` in the past gets `reminded_at = now`, so the
  first tick after deploy sends nothing.

## The loop

One 60s task alongside the runner's consumer, same event loop.

- Due: `status='open' AND stage='filed' AND remind_at <= now AND reminded_at IS NULL AND
  remind_at > now - 6h`. The 6h grace means a container down overnight does not replay the
  night on boot; anything older is marked sent without pushing.
- Payload `{title, url: "/today"}`, one push per subscription, then `reminded_at = now`.
- `reminded_at` is set once per item even when every subscription fails. A reminder is a
  moment, not a delivery guarantee; retrying it the next tick would nag.
- A push answering 404 or 410 deletes that subscription row.

`PATCH /api/items/{id}` clears `reminded_at` whenever `remind_at` changes, so moving a
reminder forward re-arms it. Without this a fired reminder can never fire again.

## Daily digest

At the first tick past `TARTIB_SUMMARY_TIME` in `TARTIB_TZ`: "N due today, M need attention".
The last sent date is stored so a restart at 08:30 neither skips nor repeats it. Sent even
when both counts are zero is wrong: skip when N and M are both 0.

## Client

- The PWA registers the worker on load. Permission is requested **only** from an "Enable
  reminders" button in Settings, never automatically: browsers require a gesture, and a
  denial cannot be re-asked in code. Settings shows the current permission state, including
  a line explaining that a denial has to be undone in browser settings.
- `sw.js` gains `push` (show the notification) and `notificationclick` (focus an existing
  client on that URL, else open one).
- Subscribing POSTs the endpoint and keys; unsubscribing deletes the row.

## Proof

- Backend tests through the fake clock in `clock.py`: one task at `remind_at` sends exactly
  one push and sets `reminded_at`; a second tick sends nothing; an edited `remind_at` re-arms;
  a reminder older than the grace window is marked sent without a push; 410 deletes the row;
  the digest sends once per day across a restart.
- Done when: a reminder set two minutes out buzzes a locked phone over a temporary HTTPS
  tunnel, and tapping it opens `/today` in the tab that is already open.
  **Outcome 2026-09-18: the buzz is proved, the tap is not.** Accepted and closed anyway; the
  second clause is recorded as a limitation below rather than met.

The tunnel is for proving this once. Subscriptions, the worker, and any iOS home-screen
install bind to that exact origin, so a new tunnel means enabling reminders again.

That turned out better than planned: the HTTPS is the private network's HTTPS, not a throwaway tunnel,
so the origin is stable and reminders keep working for as long as that network runs on both the
Mac and the phone. Nothing is exposed publicly. Real hosting is still what would make this
independent of the laptop being awake.

## Decided while building step 1

- No fake clock in `clock.py`: `Reminders.tick(now)` takes the clock as an argument instead.
- The digest's last-sent date lives in a new `app_state` key/value table.
- `reminded_at` is cleared only when `remind_at` actually **changes**. The editor resends it on
  every save, so clearing on presence alone re-fired a spent reminder after a title edit.
- Marking an item reminded must not count as a human touch, or a fired reminder would hide the
  task from the 14-day stale list. Migration 0005 narrows the `items_touch_update` trigger.
- An unusable `TARTIB_VAPID_PRIVATE` logs an error and leaves the loop off, rather than marking
  reminders sent that nobody could receive.
- A first start after `TARTIB_SUMMARY_TIME` writes that day's digest off, so installing at 22:00
  does not greet you with one.

Step 2:

- The payload carries a `tag`: `item-<id>` per reminder, `digest` for the digest. One shared tag
  made a second reminder due in the same tick silently replace the first.
- A tapped notification asks the open tab to route in place and only reloads it if nothing
  answers, so a half-typed capture survives the tap.
- A subscription minted with a superseded VAPID key is dropped and re-minted, and the dead row
  is deleted server-side: that push fails with 403, which nothing prunes on its own.
- Turning off unsubscribes the browser first, then the server. The other order could be
  re-registered by the next visit to Settings, turning reminders back on for someone who had
  just turned them off.
- Beyond the plan's "404 or 410 deletes the row": migration 0006 adds `subscriptions.failures`,
  and an endpoint that fails for any other reason 8 times in a row is dropped too. Without it a
  permanently broken endpoint is retried on every tick forever. A delivery, or the browser
  re-subscribing, clears the count.

## The tap does not open `/today` on iOS

Three attempts, each proved installed on the phone and each still landing wherever the app
was left:

1. `WindowClient.navigate()` after `focus()` -- does nothing to a frozen client.
2. `postMessage` with a reply, falling back to `navigate()` -- an iOS home-screen app is
   frozen while the worker runs and cannot answer inside any sane timeout.
3. The worker writing the destination to the Cache API for the app to pick up when it wakes,
   read on mount, `visibilitychange`, `focus`, `pageshow`, and a short burst of retries.

The third is still in the code: it is correct, it is proved on desktop, and it costs nothing.
Whether iOS dispatches `notificationclick` to the worker at all was never established -- a
diagnostic row was built to answer exactly that and the question was dropped before it was
read. That is the first thing to look at if this is ever picked up again.

What works, which is the point of the slice: the reminder arrives and buzzes a locked phone
at the time you asked, and tapping it opens Tartib.

## Status
- [x] migration + subscriptions + loop (2026-09-17)
- [x] service worker + Settings (2026-09-18)
- [x] proof + deploy (2026-09-18) -- deployed and proved on the phone, except the tap target

Step 3 can now have the keys in `.env`: enabling reminders in Settings is what step 2 added,
so a browser can subscribe before any reminder comes due.
