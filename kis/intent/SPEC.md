# Tartib SPEC

What the product does. How it is built lives in `kis/knowledge/technical.md`. Hard rules live in `kis/knowledge/rules.md`.

Status: v1.0, released and deployed 2026-09-18. Every section below is implemented. Approved changes that are not built yet live in `backlog.md`, not here.

## Capture and Item

A capture is what the user typed, stored once: `id`, `raw_text` (immutable), `source` (web | api | migrated), `created_at`, `status` (pending | done | error), `error`, `answer`.

An item is classifier output. One capture produces zero or more items.

- Shared: `id`, `capture_id`, `raw_text` (starts as the verbatim excerpt this item came from; editable by the user once filed), `space` (one of the configured spaces, or null while waiting), `shape` (`task` | `note`), `stage` (`attention` | `filed`), `created_at`.
- Task fields: `title`, `due?` (date), `remind_at?` (datetime), `starred` (bool), `status` (`open` | `done`).
- Note: no extra fields. Display uses `raw_text`.
- Each item keeps its `proposal` and `proposal_error`, even after filing, so auto-filed decisions stay inspectable.
- A filed item always has a space (database check).

## Capture

Input box at the top of every screen, or `POST /api/capture {"text": "..."}`. The capture is stored and `201 {id}` returns immediately. `GET /api/captures/{id}` reports status, items, and answer; the PWA polls it after each capture.

From the app, a capture is written to a local queue before it is sent, so the box can clear at once and nothing depends on the send working. One that cannot go out shows as "waiting to send" in Recent and goes when the network or the app comes back, oldest first. Each carries a `client_id`; `POST /api/capture` answers `200 {id}` with the capture it already has if it has seen that id, so a retry is never a second capture. Captures sent by curl or a Shortcut carry none and are never deduplicated.

## Classify

A background call to `classify(text, context)` returns a list of proposals `{text, shape, space, title, due, remind_at, confidence}`, one per independent item in the capture. Context: current datetime in `TARTIB_TZ` and the configured spaces. A task with no date in its text is given a proposed near-term one -- a day or two for follow-ups and errands, within a week otherwise -- so it reaches Today; open-ended and someday tasks, habits, and notes stay undated (since 2026-09-19).

- shape `question`: no item. The runner answers it from existing items and stores the answer on the capture.
- space outside the configured list: null, confidence capped at 0.6.
- space null or `confidence < TARTIB_AUTOFILE_CONFIDENCE` (default 0.85): `stage=attention`.
- otherwise: `stage=filed`.
- classifier off, CLI missing, failing, timing out, or invalid output: one note with space null in `attention`, `proposal_error` set, capture `status=error`.
- on startup, pending captures are re-queued, so a restart mid-classify loses nothing.

## Needs Attention decisions

- Approve: file with the stored proposal, overridden by any fields in the request. A space is required.
- Reject: discard the proposal (note, space null, dates cleared). The item stays in `attention`. Nothing is deleted.
- Delete (item page, confirmed inline): removes the item; the capture stays.

## Editing

Any filed item's `space`, `shape`, `title`, `due`, `remind_at`, `starred`, and `status` can be changed. `raw_text` cannot.

## Screens

Shell, wide screens: brand "Tartib ترتیب", pill nav Home · Inbox · Spaces · Settings with icons, a capture bar under the header on every screen, and, on every page but Home, the session while it is live (running, or ended and waiting for its outcome) as a glass card fixed just above the ask bar, in the same 720px column, the same 10px above it on every page, with no list of earlier sessions -- those are Home's; on Home it is an ordinary Session card -- under Needs attention on a wide screen, first on a phone -- in every state -- red, a countdown ring while running, the outcome buttons and the last three sessions once stopped, and when none runs it stays as a quiet card listing the last three, each with ▶ to run it again, and Start for a fresh one (capture bar: auto-growing box, mic when the browser supports on-device speech, Add). Enter or Add saves, Shift+Enter adds a line; the box clears at once, a toast says "Saved" then the outcome; a question capture navigates to Home and shows its answer. The ask bar is on every page (since 2026-09-19; before, Home and Inbox only).

Shell, phones (since 2026-09-20): no header and no bars. A fixed bottom bar -- Home, Inbox, ⊕, Spaces, Settings -- holds the nav under the thumb; ⊕ opens a sheet with two modes, Capture and Ask, which is where the capture box and the ask bar live on a phone (Escape or a tap outside closes it; a capture closes it on success; a question handed over from a space's search box opens it in Ask mode holding the question). A page shows one line of heading -- its title and its actions -- since the bar already says which section it is. The page reserves the top safe area itself, since there is no header to do it. An item opens in a sheet over the list it was tapped in (`?item={id}`, so Back closes it) rather than as its own page. Every control is at least 44px. `c` focuses capture anywhere; `/` focuses search on the Spaces screens.

Header convention: the **eyebrow** names the page only when the title does not; the **subtitle** says what the page is for and never carries a count (counts live in the card header that owns them); **Back** is one control, history-aware with a per-page fallback.

```text
Route              Back    Eyebrow    Title                    Subtitle
/                  —       DASHBOARD  <today's date>           Today, what needs you, and what you captured.
/inbox             —       —          Inbox                    Approve what the classifier proposed, or file it yourself.
/inbox/stale       —       —          Inbox                    Open tasks nobody has touched in a while.
/inbox/recent      —       —          Inbox                    Everything you captured, newest first.
/spaces            —       —          Spaces                   Where things live. Search across all, or end with ? to ask.
/settings          —       —          Settings                 How this copy of Tartib is set up.
/spaces/{name}     Back    SPACES     <space name>             Brief, tasks, and notes in this space.
/items/{id}        Back    —          —                        — (the card holds the item)
```

1. Home `/`: Today (open tasks due today or overdue, starred, passed reminders, or worked on in a session today; starred first; today's session count per task and in total, with a Start a session button), Needs attention (top 3 of queue then stale, "View all", and a line naming the most recently touched space), Recent (last 3 captures, "View all"). Two columns from 900px that stack independently -- Today then Recent on the left, Needs attention then Session on the right; on a phone the order is Session, Today, Needs attention, Recent.
2. Inbox: three tabs in the nav's pill style at the right of the title (below it on phones), each its own route so Back moves between them, with a count on the first two -- Needs attention `/inbox`, Stale `/inbox/stale`, Recent `/inbox/recent` (since 2026-09-19; `/inbox/attention` redirects to `/inbox`). Needs attention: every waiting item as a decision card, newest first, "Not now" sending one to the end (text, proposal sentence with tappable words, the reason it waits -- AI failed, proposal rejected, no space matched, or unsure with its confidence -- Approve, Not now, "…" with "Tell it why…" and Open -- a reason sends the item back to the classifier, and a confident answer files itself; since 2026-09-19 there is no Reject); Enter approves the first. Stale: open filed tasks untouched 14+ days. Recent: captures newest first, 50 at a time with "Load more", leaving out what waits in Needs attention.
3. Spaces `/spaces`: title row with "+ New space" at the right (lowercase, digits, dashes, 24 max). Search across everything, results grouped by space; a question goes to the ask bar. Cards: name, "4 open · 12 notes", last activity, overdue dot; Unfiled muted, links to Inbox. A card opens `/spaces/{name}`: Back, title row with "+ Add" (file a task or note straight into this space, a due date for tasks, no classifier) and "…" (filing policy -- "Files when sure", "Always ask me", "Always file here", the current one ticked and named in the subtitle when it is not the first; Rename carries items; Delete only when empty). Then the brief as a strip that opens on a tap, the search box (a question -- the Ask button, a trailing "?", or Cmd/Ctrl+Enter -- goes to the ask bar at the foot with this space already selected, and the box clears; since 2026-09-20 answers appear only there), and two pill groups in the nav's style with counts -- All, Tasks, Notes on the left, Done, Sessions on the right -- over one dense list of lines, each led by what it is: a working checkbox for a task (ticking it off where it stands), the note glyph for a note, a clock for a session; `j` and `k` walk it. From 1100px the item opens beside the list (`?item={id}`, so Back steps through what was opened and edits there refresh the list); narrower, a line opens `/items/{id}`. The Sessions chip lists this space's own sessions. (This is the Panes layout; the card column and the tree were tried beside it in slice 21 and dropped on 2026-09-20.)
4. Settings `/settings`: Appearance (theme), Classifier (Codex on/off, threshold), Device (voice capture, session sound for this device -- bell, kitchen, wood or off, timezone, reminders worker version, installed), Reminders (enable or turn off push; permission is only ever asked from that button, and a blocked browser is told it has to be undone in browser settings), Spaces (configured list), Account (sign out). Read-only except theme, session sound, reminders, and sign out.
From 1100px wide a space page splits: the list on the left, the open item on the right (`/spaces/{name}?item={id}`, so Back steps through what was opened); a row click swaps the item and edits there refresh the list. Narrower, rows open the item page. (Since 2026-09-19.)
5. Item page `/items/{id}`: a Thoughts card under the text -- an append-only log of dated entries, oldest first, with a box to add the next; rows show the count, search finds an item through them, and Ask and the space brief read them (since 2026-09-19). Then the item's text (editable via "…" > Edit text or double-click), status chips, the space name linking to its space, "File it" (while waiting) or "Edit" (filed) and "Proposal" as accordions, open while waiting and closed once filed; the Proposal shows the original capture text when it differs. "…" also holds Delete with an inline confirm.
6. Login: one password field.

Routes from earlier versions still resolve; the redirect map is in `../knowledge/technical.md`.

Rows everywhere come from one component: leading glyph (checkbox for a filed task, alert for something awaiting a decision, note for a note), title linking to the item page, muted meta "space · 2h ago" (or "needs attention · 70%"), "due Fri, Sep 18" at the right for dated tasks, overdue rows tinted, the star always visible on tasks, hover or long-press reveals edit.

## Out of scope

Projects, tags, multi-user. Push and pomodoro left this list on 2026-09-17 under the rule 4 carve-outs.

Offline capture queue left it on 2026-09-18, in slice 15. The argument is the one the other two
were made on: rule 4 exists so that Tartib does not nag, and a capture box that quietly drops
what you typed underground is not nagging, it is lying. It is also the smallest of the three in
what it adds to the product -- no new screen, no new decision to make, nothing that pushes. A
capture is written down before it is sent, shown as waiting until it goes, and carries a
`client_id` so a retry is recognised rather than duplicated. Offline *reading* stays out of
scope: the app still needs the network to show you anything.
