# Tartib SPEC

What the product does. How it is built lives in `kis/knowledge/technical.md`. Hard rules live in `kis/knowledge/rules.md`.

Status: v1.0, released and deployed 2026-09-18. Every section below is implemented. Approved changes that are not built yet live in `backlog.md`, not here.

## Capture and Item

A capture is what the user typed, stored once: `id`, `raw_text` (immutable), `source` (web | api | migrated), `created_at`, `status` (pending | done | error), `error`, `answer`.

An item is classifier output. One capture produces zero or more items.

- Shared: `id`, `capture_id`, `raw_text` (the excerpt this item came from, as the classifier returned it -- it is asked for a verbatim slice, but that is an instruction, not a check; editable by the user once filed), `space` (one of the configured spaces, or null while waiting), `shape` (`task` | `note`), `stage` (`attention` | `filed`), `created_at`, `updated_at` (drives the stale-save check below), `thought_count`, `feedback` (one dated line per "tell it why"), `duplicate_of` and `wait_reason` (see Classify).
- Task fields: `title`, `due?` (date), `remind_at?` (datetime), `starred` (bool), `status` (`open` | `done`).
- Note: no extra fields. Display uses `raw_text`.
- Each item keeps its `proposal` even after filing, so an auto-filed decision stays inspectable. `proposal_error` is cleared when the item is filed, because it no longer describes the item -- the failure itself is not lost, since it is also recorded on the capture's `error`, which filing never touches. (Decided 2026-09-22; this line used to promise the error survived on the item.)
- A filed item always has a space (database check).

## Capture

Input box at the top of every screen, or `POST /api/capture {"text": "..."}`. The capture is stored and `201 {id}` returns immediately. `GET /api/captures/{id}` reports status, items, and answer; the PWA polls it after each capture.

From the app, a capture is written to a local queue before it is sent, so the box can clear at once and nothing depends on the send working. One that cannot go out shows as "waiting to send" in Recent and goes when the network or the app comes back, oldest first. Each carries a `client_id`; `POST /api/capture` answers `200 {id}` with the capture it already has if it has seen that id, so a retry is never a second capture. Captures sent by curl or a Shortcut carry none and are never deduplicated.

## Classify

A background call to `classify(text, context)` returns a list of proposals `{text, shape, space, title, due, remind_at, confidence}`, one per independent item in the capture. Context: current datetime in `TARTIB_TZ`, the configured spaces, and -- since slice 26 -- what already lives in each of them: per-space counts and the most recent few items, a task by its title and a note by the first 60 characters of its text. It is shown so that a capture can be filed where comparable things already are. Since slice 27 it is also shown your own **house rules** -- filing rules in your words, which outrank its reading of where something belongs but cannot change how it replies -- and up to five recent filings as **examples**, corrections first. A task with no date in its text is given a proposed near-term one -- a day or two for follow-ups and errands, within a week otherwise -- so it reaches Today; open-ended and someday tasks, habits, and notes stay undated (since 2026-09-19).

- shape `question`: no item. The runner answers it from existing items and stores the answer on the capture.
- A proposal may **ask you something** instead of guessing (since 2026-09-21): one question about one field -- which space, or task or note -- with two to six answers as buttons. An item that asks never files itself, whatever its confidence: it is waiting on you by definition. Answering fills the proposal in; approving is still a separate act. Options naming a space that does not exist are dropped, and a question with fewer than two real answers is dropped whole.
- space outside the configured list: null, confidence capped at 0.6.
- A proposal may **name a space that does not exist yet** (since 2026-09-21): a proposal only. Naming it creates nothing and files nothing -- the item waits exactly as an unknown space makes it wait -- and a name that already exists, or fails the Spaces page's rules, is dropped. Approving it is what creates the space and files the item there. See rule 7.
- A proposal may **name an item it duplicates** (since 2026-09-21). For each capture the classifier is shown the filed items that resemble it, labelled `i1`, `i2` and so on -- never their ids, so a label it invents resolves to nothing. The match is recorded on the item as `duplicate_of` whether or not anything else happens. With `TARTIB_DUPLICATE_PARK` on, a suspected duplicate waits instead of filing and says what it looks like; **it is off**, so today the verdict is recorded and nothing is held back. Nothing is ever merged. **A filed item does not show its match** -- the "Looks like #N" line appears only on a waiting card. Decided 2026-09-22: while parking is off the verdict is being gathered to judge how often it is wrong, and surfacing an unjudged verdict on every filed item would show the owner its false positives as though they were findings. It becomes visible where it matters, on the card it holds back, once parking is switched on.
- Whether a proposal files itself is decided by **the space's filing policy first**: `file` files at any confidence, `ask` never files, and only `auto` -- the default -- compares `confidence` against `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85). A null space never files, whatever the policy.
- **A capture that splits files none of its pieces** (since slice 30): more than one item from one capture -- questions aside -- means every piece waits, whatever its confidence and whatever the space's policy. Whether it was really several things is the owner's call. The classifier is told that a heading over lines that belong under it is one note; it splits only separate things to do, or unrelated facts.
- A waiting item records why, as `wait_reason`: `split` (one of several pieces from one capture; it wins over the others), `no_space`, `low_confidence`, `asked` (it has a question for you), `duplicate`, or `whole` (kept as one, see Needs Attention decisions).
- classifier off, CLI missing, failing, timing out, or invalid output: one note with space null in `attention`, `proposal_error` set, capture `status=error`.
- on startup, pending captures are re-queued, so a restart mid-classify loses nothing.
- **A failed capture is retried** (since 2026-09-19): every 15 minutes, and straight after any capture classifies, up to 3 attempts. A retry replaces the fallback note, so it only happens while that note is exactly as the fallback wrote it -- no space, title, date, star, edit, **thought or redo reason**. Anything a person added means they have started on it, and a retry would throw that away. "AI not configured" is never retried.
- A capture holding more than one question has only its first answered.

## Ask

A question is answered only from the person's own items, never from what the model knows. Retrieval is FTS5 over item text and the thoughts attached to it, best first, capped at 20. When nothing matches at all, the answer is built from the 20 most recent items rather than from nothing.

- When the question's own words match little or nothing **and the database holds more than they matched**, Codex proposes 3 to 5 search terms and retrieval runs again on those (since 2026-09-21). One extra call, spent only where the cheap path failed: a question whose own words already find enough costs exactly one call, as it always did, and a database with nothing left to find spends nothing. A failed expansion is not a failed question -- the answer comes back from whatever the first pass found.
- The API reports whether anything matched and whether proposed terms are what found it (`matched`, `expanded`); **the app does not show either**. Decided 2026-09-22: this line used to promise the answer said so, and it never did. The fields stay in the payload for a later screen that wants them. "Expanded" is a fact about the answer, not about the spend: expansion that runs and finds nothing reports `false`.
- **One turn of context.** The client sends the previous question and the items that answered it, so "what about the second one?" has a referent -- the server keeps no conversation of its own. One turn, not a history, and dismissing an answer ends it. Ask becoming continuous is a later, larger thing.

## What the AI costs

Since 2026-09-22 every AI call is recorded: which kind (classify, ask, the search-term expansion),
the model, the token counts, how long it took, whether it failed and in the CLI's own words, and
what was in the prompt -- its size and how many candidates, examples and real corrections it
carried. The subscription limit is its own kind of failure, recorded with the reset time the CLI
reports. Settings shows the totals, a per-capture average, and an estimated cost.

The cost is **an estimate twice over** and says so: the subscription reports no money at all, and
the rates are list prices. They ship with the app, and are refreshed at most once a day from a
public price catalogue. That is one of three outbound connections Tartib makes: the AI CLI, Web
Push to the browser vendors' push services when reminders are on, and this. The app works with
this one blocked; it then costs from the shipped rates. Nothing here is a
budget or a limit: it records and never enforces.

## Needs Attention decisions

- Approve: file with the stored proposal, overridden by any fields in the request. A space is required.
- Tell it why (since 2026-09-19, replacing Reject): a sentence of reason re-runs the classifier on the item's text with it, the reason is kept on the item, and the new proposal follows the normal rules -- a confident one files itself. Nothing is deleted.
- Keep as one (since slice 30, on a split piece): replaces all of that capture's pieces with one waiting note holding the capture's whole original text. It proposes the pieces' space when they all agree and otherwise asks between their spaces; it is always a note, and it never files itself. Offered only while every piece is untouched -- not approved, edited, answered, redone, given a thought or worked on in a session -- the same spirit as the retry rule. A deleted piece does not block it, and its words come back with the rest.
- Delete (item page, confirmed inline): removes the item; the capture stays.

## Markdown

Item text, thought entries, Ask answers and a space brief render as markdown (since 2026-09-20): headings, lists, emphasis, code, quotes, links and tables. The stored bytes are never rewritten -- rendering is presentation only -- and a row's headline shows the first line with its syntax stripped, because a row is one dense line. Raw HTML in any of them renders as the characters it is, never as markup. **A remote image is not loaded** (since 2026-09-22): its description and address are shown as text instead. Item text, answers and briefs are written by the model from text that may not be the owner's, and an injected image is a way for what the model saw to leave the device; a content security policy enforces the same thing for anything the renderer might miss.

## Offline

Since 2026-09-21 the app works without the network. Every screen but Settings shows the last
thing it was given and says how old that is -- *"Offline · showing what was here 2h ago."* --
rather than going blank; online it says nothing, because the network answered and the data is
live. Settings reads out configuration rather than data, and does not carry the line.

Four things work with no network: ticking a task done, starring it, editing its text, and adding
a thought. Each is written down, shown as **waiting to send**, and sent when the network returns,
in the order it was made. A change that was refused because the item moved on elsewhere keeps
your words and asks Reload or Overwrite, the same question a live save asks.

What deliberately does not work offline says so instead of failing quietly: starting a session
(the server holds the clock), asking a question (it needs the classifier), approving or
re-asking a proposal, filing an item directly, deleting, and creating, renaming or deleting a
space. Nothing is ever classified on the device.

Counts are the one place the app is knowingly behind: a queued change shows on the item wherever
it appears, but tiles, counts and a space's brief are computed by the server and do not move
until what is queued has been sent.

Editing text offline needs one unhurried moment online first, because the editor arrives as its
own chunk and the app only holds what it has already fetched.

## Editing

Any filed item's `space`, `shape`, `title`, `due`, `remind_at`, `starred`, and `status` can be changed, and so can its `raw_text` (since 2026-09-17; rule 1 keeps the *capture's* text immutable, not the item's). Since 2026-09-20 the text is edited by tapping it: there is no mode to enter and no button to enter one, the editor arrives on that tap, and it saves itself as you pause. A save refused as stale offers Reload or Overwrite without taking your words away.

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
2. Inbox: three tabs in the nav's pill style at the right of the title (below it on phones), each its own route so Back moves between them, with a count on the first two -- Needs attention `/inbox`, Stale `/inbox/stale`, Recent `/inbox/recent` (since 2026-09-19; `/inbox/attention` redirects to `/inbox`). Needs attention: every waiting item as a decision card, newest first, "Not now" sending one to the end (text, proposal sentence with tappable words, the reason it waits -- AI failed, proposal rejected, split from one capture into N (with a Keep as one button while that is allowed), kept as one, no space matched, has a question for you, looks like something already here, or unsure with its confidence -- the capture's own words opening the item, then Approve, Not now and "Tell it why…" -- a reason sends the item back to the classifier, and a confident answer files itself; since 2026-09-19 there is no Reject, and since 2026-09-20 no "…" menu either); Enter approves the first, **except while focus is in a field** -- Enter there commits what you were typing and approves nothing. A card whose classifier asked a question shows it above the sentence, with the answers as buttons; one that looks like a duplicate says *"Looks like #N already here. Filing this keeps both."*; one proposing a new space offers it as a dashed `+ name` beside the real ones. Stale: open filed tasks untouched 14+ days. Recent: captures newest first, 50 at a time with "Load more", leaving out what waits in Needs attention.
3. Spaces `/spaces`: title row with "+ New space" at the right (lowercase, digits, dashes, 24 max). Search across everything, results grouped by space; a question goes to the ask bar. Cards: name, "4 open · 12 notes", last activity, overdue dot; Unfiled muted, links to Inbox. A card opens `/spaces/{name}`: Back, title row with "+ Add" (file a task or note straight into this space, a due date for tasks, no classifier) and, since 2026-09-20, a visible AUTO / ASK / FILE segment for the filing policy with Rename and Delete beside it, rather than a "…" menu (Rename carries items; Delete only when empty). Then the brief as a strip that opens on a tap, the search box (a question -- the Ask button, a trailing "?", or Cmd/Ctrl+Enter -- goes to the ask bar at the foot with this space already selected, and the box clears; since 2026-09-20 answers appear only there), and two pill groups in the nav's style with counts -- All, Tasks, Notes on the left, Done, Sessions on the right -- over one dense list of lines, each led by what it is: a working checkbox for a task (ticking it off where it stands), the note glyph for a note, a clock for a session; `j` and `k` walk it. From 1100px the item opens beside the list (`?item={id}`, so Back steps through what was opened and edits there refresh the list); narrower, a line opens `/items/{id}`. The Sessions chip lists this space's own sessions. (This is the Panes layout; the card column and the tree were tried beside it in slice 21 and dropped on 2026-09-20.)
4. Settings `/settings`: Classifier (Codex on/off, the auto-file threshold, **what the AI has done** -- calls, tokens, time spent waiting, an estimated cost that says it is an estimate, and how full the subscription's window is when the CLI reports it -- **learning from** N corrections, and the **house rules** editor), Device (voice capture, session sound for this device -- bell, kitchen, wood or off, timezone, reminders worker version, installed), Reminders (enable or turn off push; permission is only ever asked from that button, and a blocked browser is told it has to be undone in browser settings), Spaces (configured list), Account (sign out). Editable: house rules, session sound, reminders and sign out; the rest reads out. There is **no theme setting** -- one theme, bronze, since the picker and the other palettes were taken out.
From 1100px wide a space page splits: the list on the left, the open item on the right (`/spaces/{name}?item={id}`, so Back steps through what was opened); a row click swaps the item and edits there refresh the list. Narrower, rows open the item page. (Since 2026-09-19.)
5. Item page `/items/{id}`: a Thoughts card under the text -- an append-only log of dated entries, oldest first, with a box to add the next; rows show the count, search finds an item through them, and Ask and the space brief read them (since 2026-09-19). Then the item's text, rendered as markdown and edited in the same place -- tap the words and the caret lands where you tapped (since 2026-09-20) -- then status chips, the space name linking to its space, "File it" (while waiting) or "Edit" (filed) and "Proposal" as accordions, open while waiting and closed once filed; the Proposal shows the original capture text when it differs, and shows it verbatim rather than as markdown, because what it is for is the bytes. Start session (open tasks only) and Delete are visible pills in the header, Delete with an inline confirm -- they were behind a "…" until 2026-09-20, and the third pill, Edit, went with it when tapping the text became the way in.
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
`client_id` so a retry is recognised rather than duplicated.

Offline reading and offline editing left the list on 2026-09-21, in slice 25, on the argument
slice 15 deferred rather than refused: an app that shows you nothing the moment the network goes
is not protecting you from stale data, it is withholding what it already has.
