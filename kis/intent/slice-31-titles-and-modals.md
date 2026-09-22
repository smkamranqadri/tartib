# Slice 31: one title, one control shape, and questions in a modal

Planned 2026-09-22, from the first-day feedback on `v2.0`. Phase mode: three phases, each
committed and proved on its own, in this order.

## What was reported

- **The title** (owner): *"don't know title where note or task render, it duplicate and i can't
  edit it."* A task's AI title shows as a heading above the text, in the row, and in the Edit
  section's Title field, and only the last is editable. A note has no title.
- **Delete** (owner): *"should ask to delete note or task in modal not in note's body."*
- **The switches** (owner, three screenshots): the Task / Note switch in "+ Add" and the space
  page's AUTO / ASK / FILE should look like the All / Tasks / Notes pills.

## Decided with the owner, 2026-09-22

1. **The first line of the text is the title**, for tasks and notes alike. It is shown **once**:
   the item page drops the separate heading, and draws the text's first line as a title.
2. **The AI's task title is prepended as line one** of the task's text when it differs from the
   excerpt's first line -- on every new capture, and once for existing tasks. Offered stopping
   titles altogether (rule 1 whole, longer rows) and offering the title for acceptance; the owner
   chose prepending. **This amends rule 1**: the AI now writes a task's first line. The
   capture's `raw_text` stays immutable and whole.
3. **Every question in the app asks in a modal**: deleting an item, deleting a space, the session
   outcome, the changed-elsewhere Reload / Overwrite, and -- newly asked -- Sign out and Clear
   house rules. Offered deletes only; the owner chose everywhere. This ends "no modal, here or
   anywhere".
4. **`.seg` becomes the pills** everywhere it is used.

## Phase 0: one control shape

`.seg` (8px radius, raised `--panel` highlight) has three users: the "+ Add" Task / Note switch
(`AddItemForm.tsx`), the filing policy (`Space.tsx`), and the chime sound (`Settings.tsx`). They
take the `.pills` look: fully rounded, the active one filled `--fg` on `--bg`. Check: each renders
with the pills' radius and active colours, phone and desktop, and the 44px floor holds.

## Phase A: the first line is the title

- `title` stays a column but becomes **derived**: the store sets it to the text's first line
  (flattened) on every insert and text edit. As built, only for tasks: a note keeps `title` null
  and everything that names one already reads its first line. Reminders, sessions, Ask's item
  header and the classifier's context all read `title`, so they need no change.
- On filing (runner, redo, reclassify): a task whose proposed title differs from the excerpt's
  first line is stored as `title + "\n\n" + excerpt`. **Redo** replaces line one only while it is
  still exactly the previous AI title; once you have edited it, it is yours.
- **Migration 0018**: every task whose title differs from its first line gets the title prepended
  the same way. Idempotent, and it must not bump `updated_at` (the Stale list reads it). Local:
  25 of 40 once case is ignored (36 by exact comparison); count the deployed database on a copy
  before deploying.
- Item page: the `item-title` heading goes, the Edit section's Title field goes, and the first
  line is drawn as a title in the rendered view **and** the editor, so tapping in does not jump.
  A first line that is a list item or a checklist box is not styled as a title.
- The capture hint "The first line becomes the title" is reworded to something true.

## Phase B: questions in a modal

One `Modal` (native `<dialog>`, Escape or a tap outside cancels, focus returns to the control
that opened it) replaces `Confirm.tsx`. The six questions above use it. **Not** moved: Inbox
decision cards and the classifier's question buttons (they are the page, not an interruption),
the update bar (an offer), and "Not saved · Retry".

## Acceptance

- A task captured as "need to call Ali about the car insurance renewal" with AI title "Call Ali"
  is stored as "Call Ali\n\nneed to call Ali about…"; its row, reminder and session read "Call Ali".
- Editing line one changes the title everywhere; a note's title is its first line.
- Migration: prepends only where the title differs, a second run changes nothing, `updated_at`
  unchanged.
- The item page shows the title once, styled as a title, and nothing jumps on tapping in.
- Each of the six questions opens in a modal; Escape cancels; nothing happens without confirming.
- Backend suite green (count recorded in State after the run). **`npm run ui` gains committed
  checks** for a save not reloading the note, ticking a box, the title shown once, and a delete
  modal -- the gap the 2026-09-22 KIS check named.

## Risks

- The migration rewrites the text of dozens of live tasks, and the deployed database has no
  backup. A one-off copy of `tartib.db` just before this deploy is the cheap guard.
- The conflict question can now open right after a pause in typing, because autosave raises it.
  More abrupt than the strip; accepted with decision 3.
- `<dialog>` needs iOS 15.4 or later: check on the phone.

## Done, 2026-09-22 (deployed as `v2.1` the same day)

- **Phase 0** (`2e5f8bd`): the three switches match the filter pills' computed radius, colours and
  height, desktop and phone.
- **Phase A** (`b5ba4a5`): 308 backend tests, 9 new in `test_titles.py`. A sabotage that keeps the
  touch trigger during 0018 turns its `updated_at` test red. Migration dry run on a copy of local:
  25 of 40 tasks prepended, no `updated_at` moved, every stored title equal to `title_of`. The
  rendered and editor title lines measured identical on a phone.
- **Phase B**: the six questions checked in Chrome at phone size -- the stale save stays open
  through Escape and Keep mine saves your words; the session modal opens once, and Later holds
  across in-app navigation *and* a reload; space delete, Sign out and Clear confirm and cancel.
  **Found on the way, older than this slice:** a space's header ran 428px on a 390px phone and
  hid Delete off the screen (the page clips, so the overflow check never saw it); fixed, and S22
  now checks every header control is on screen.
- `npm run ui` **14/14**, with five new committed checks (F1, F2, S31 title, S31 delete modal,
  and S27 now proving Clear asks first).
- **Before deploying: dry-run 0018 on a copy of the live database** and look at what it will
  prepend. Some additions are near-copies ("Call the dentist to book a cleaning" over "Call the
  dentist and book a cleaning"); that is the owner's chosen rule working, not a bug.
- Not settled here, for the phone: whether `<dialog>` behaves on the owner's iOS, and whether a
  modal for every question feels right in use.
