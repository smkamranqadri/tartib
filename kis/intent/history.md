# Slice history

What each slice changed, newest first. All are done and deployed. Current truth lives in
`SPEC.md` (product), `../knowledge/technical.md` (how it is built), and `../knowledge/rules.md`
(hard rules). Where a slice below disagrees with those, they win; the full plans are in git.

Scope rules changed on 2026-09-17: rule 4 stopped banning push and pomodoro, and SPEC's Out of
scope list dropped the ask feature and the Claude fallback, both of which had already shipped.

- **11 · push reminders** (2026-09-18) Web Push for reminders the user set plus one daily digest: migration 0005 (`items.reminded_at`, `subscriptions`, `app_state`) and 0006 (`subscriptions.failures`), a 60s loop beside the runner's consumer with a 6h grace, `push.py` as the transport, `python -m tartib.vapid` for keys, and a Settings card that asks for permission only on a click. Deployed and proved on a real phone over HTTPS on a private network; the notification buzzes a locked screen, but tapping it does not navigate to `/today` on iOS.
- **10 · consistency** (2026-09-17) One header convention: the eyebrow names the page only when the title does not, the subtitle says what the page is for and never carries a count, Back is one history-aware control. Inbox took its drill-downs at `/inbox/attention` and `/inbox/recent`. Extracted `Row`, `Menu`, `Confirm`, `NameForm`, `Status`; `Card` gained a collapsible mode. One primary button class.
- **9 · inbox cards** (2026-09-17) Inbox shows the newest waiting items as decision cards with Enter on the first. Recent pages by capture id. Spaces dropped its chip bar; each space opens on its own page. Star always visible on task rows.
- **8 · feedback round** (2026-09-17) Spaces became a table the user manages. A filed item's text became editable and deletable. Brief cache keyed on add or remove only. Capture bar grew multi-line.
- **7 · dashboard restyle** (2026-09-17) Took the structure and visual language from the user's screenshots: header capture bar, icon nav, eyebrow and title, section cards with counts, teal accent, Settings page, stale tasks, voice capture.
- **6 · spaces view** (2026-09-17) Added `items.updated_at`, the `briefs` table, the space summary and per-space AI brief.
- **5 · UI simplification** (2026-09-17) Cut the app to a capture-first Home, a flat Today, and a one-at-a-time decision queue.
- **4 · classifier fixes** (2026-09-17) Captures stored once; items became classifier output referencing `capture_id`; one capture can split into many items; `question` shape answers instead of filing; spaces moved to config; the `inbox` space was removed.
- **2 · retrieval** (2026-09-17) FTS5 search, the item page, and `POST /api/ask` answering only from the user's own items.
