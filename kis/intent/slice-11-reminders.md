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

The tunnel is for proving this once. Subscriptions, the worker, and any iOS home-screen
install bind to that exact origin, so a new tunnel means enabling reminders again. Living
with reminders needs real HTTPS hosting, which is not in this slice.

## Status
- [ ] migration + subscriptions + loop
- [ ] service worker + Settings
- [ ] proof + deploy
