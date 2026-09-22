# Slice 33: links between items

Planned 2026-09-22 with the owner, from the backlog entry approved that day ("we definitely need
links"). Phase mode: A and B each committed and proved on their own; C is direction only and gets
its own plan later.

## What was reported

Moving old notes in by hand: a CapRover setup note includes the Docker setup note, which includes
the server setup note -- one note should open the next, and the one linked to should show what
links to it. And a task to build a console app belongs to its own work but also to `coding`.

## Decided with the owner, 2026-09-22

1. **A link is `[[Title]]` in the text**, Title being the target's first line (since slice 31 the
   first line is the title). Typing `[[` in the editor opens a picker of items by first line,
   with the space shown; typing it by hand works too. Across spaces, tasks and notes alike.
   Offered `[[#42]]` (rename-proof, unreadable raw); the owner chose titles.
2. **Renaming rewrites links.** Changing an item's first line rewrites every `[[Old]]` in other
   items to `[[New]]` in the same save. Offered visible breakage instead.
3. **A missing target dims** ("not found"); **two items with the same first line: the most
   recently touched wins**, and the picker shows the space so they can be told apart.
4. **"Linked from" card** on the item page, hidden when empty. No counts on rows.
5. **A link to a space: `[[space:coding]]`.** The space page gets a **"Linked here"** section,
   apart from its own items; the item keeps its one space. Offered items in several spaces (much
   larger: filing, counts, briefs, classifier) and mixing linked items into the list; the owner
   chose the separate section.
6. **The classifier will propose links, last** (phase C). Accepting appends `Related: [[X]]` to
   the text, so every link has one form. The owner chose to have such an item **wait in Needs
   attention**. It comes after the duplicate verdicts are judged, so the classify prompt does
   not change while that data and the house-rules comparison are being gathered.

## Challenges raised, and where they landed

- **A rewrite writes to other items.** Their `updated_at` must move, so an editor open on one of
  them gets the "Changed elsewhere" modal instead of silently saving the old link back. The
  captures stay as typed (rule 1).
- **Notes store no title** (slice 31: a note's `title` is null). Links need a key for every item,
  kept by the Python write path -- slice 31 learned that an SQL approximation of the first line
  is not the rule.
- **Autocompletion is off in the editor** (`autocompletion: false`); it comes back for `[[` only.
- **Phase C waiting in Needs attention** holds a task off Today until answered, and could fill the
  inbox with everything that resembles something. Recorded as the owner's direction; to be
  reopened with the duplicate data when C is planned.

## Phase A: `[[Title]]`

- Migration 0020: a link key per item (the normalised first line, `same_title`'s notion of equal),
  set by `store` on every insert and text write, backfilled in Python. Whether links are a table
  written on save or found on read is decided at the start of A, by what backlinks and the
  rewrite need.
- Render: a `[[…]]` token in `markdown.ts` / `Markdown.tsx`, a link to the item or dimmed when
  nothing matches; not inside code. The model-written brief and Ask answers render it too, as
  text they quote.
- Picker: CodeMirror completion on `[[`, from an items-by-first-line search, showing the space.
- "Linked from" on `ItemPage.tsx`: rows of the items whose text links here.
- Rename rewrite in the store's text-write path, one transaction, moving each touched item's
  `updated_at`.

## Phase B: `[[space:name]]`

- The same token with a `space:` prefix; the picker offers spaces after `[[space:`.
- "Linked here" on `Space.tsx`: items elsewhere that link to the space.
- Space rename (`spaces.py`) rewrites `[[space:old]]`; space delete leaves them dimmed.

## Phase C: the classifier proposes (direction only)

Planned after the duplicate verdicts are judged (State, Next). What is decided: accept appends
`Related: [[X]]`, and the item waits in Needs attention.

## Out of scope

Items in several spaces; link counts on rows; links in thoughts; the item graph (unblocked by
this, stays in the backlog).

## Acceptance

A:
1. `[[X]]` opens X; a missing X renders dimmed; with two items titled X, the newest opens.
2. `[[` in the editor offers items with their space and inserts `[[X]]`.
3. X shows "Linked from" listing the item that links to it, and nothing when none does.
4. Renaming X rewrites the link in the linking item; an editor open on that item gets the conflict
   modal on save, not a silent revert; the capture's text is unchanged.
5. `[[…]]` inside a code block is left as text.

B:
6. `[[space:coding]]` lists the item under coding's "Linked here", and it is not counted among
   coding's own items.
7. Renaming coding rewrites the link; deleting coding leaves it dimmed.

## Verification

- `pytest`: 315 plus a new `test_links.py`, all green.
- `npm run ui`: 15 plus checks for render, picker, "Linked from" and "Linked here".
- Looked at on 390px and desktop.
- No AI call in A or B.
- Code review of the rename rewrite before deploy: it writes to many items in one save.

## On ship

`technical.md`: the link key, the grammar, the rewrite rule. SPEC: item page and space page.
Backlog: the links entry leaves; the item graph drops "blocked on links". history.md.
