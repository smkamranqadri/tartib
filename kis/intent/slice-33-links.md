# Slice 33: links between items

Planned 2026-09-22 with the owner, from the backlog entry approved that day ("we definitely need
links"). Phase mode: A and B each committed and proved on their own; C is direction only and gets
its own plan later.
**Phases A and B built and verified 2026-09-22 (Proof, below); C in progress. Nothing of 33 is deployed.**

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

## Phase C: the classifier proposes links (planned 2026-09-22, Standard)

The owner chose to build it now rather than after the duplicate judgment, **behind a switch** so
the data being gathered stays clean. Decided:

- `TARTIB_LINK_PROPOSALS`, off by default. Off, the classify prompt is byte-for-byte today's;
  `ai_calls` records per call whether it was on (migration 0021).
- Candidates are only the similar items already shown for duplicates (`i1`..`i8`); a new
  `related` field names at most 2, resolved like `duplicate_of`, invented labels dropped, and an
  item named as the duplicate is not also related.
- The item **waits unfiled** in Needs attention (reason `linked`) -- except in a FILE space,
  which files as always; the proposal is kept in `proposal_json` either way and is not shown on
  filed items, like the duplicate verdict.
- The waiting card shows each proposed link as a chip, on by default; filing appends
  `Related: [[A]], [[B]]` for the chips kept, none when all are off.
- Two eval cases (one should link, one should not), run once each on the live model with the
  switch on: 2 calls.

Accepted consequences: a task waiting for a link is off Today until answered (the switch backs
out); "related" and "duplicate" must be kept apart by the prompt, which the eval pair tests.

Acceptance (C):
8. Switch off: the prompt is unchanged (asserted) and nothing waits for a link.
9. Switch on, reply `related: ["i2"]`: the item waits with reason `linked` and the chip.
10. Chip kept: the filed text ends `Related: [[Title]]` and the target lists it under Linked from;
    chip dropped: no link.
11. FILE space: files, proposal kept. Invented label: ignored.
12. `ai_calls` records the switch per call.

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

## Proof: phase A (2026-09-22, local)

- As built: migration 0020 adds `item_keys(item_id, key, title)` and `item_links(source_id,
  target)`, apart from `items` so the touch trigger never fires for bookkeeping; written by
  `store.index_links` from `insert_item` and `update_fields` (every text write goes through one
  or the other, checked), cascaded on delete, rebuilt whole at startup (`reindex_links`). The key
  is `link_title`: `title_of`, with a link inside the line read as its words, so "[[Alpha]]
  notes" is named "Alpha notes". `GET /api/items/{id}` adds `links` (each `[[…]]` as written, to
  an id or null) and `linked_from`; `/api/links/suggest` and `/api/links/resolve` are new
  (`links.py`). The client lexes `[[…]]` as its own marked token in a dedicated `Marked`
  instance: `marked.lexer(text, options)` drops what `marked.use` registered, which the first
  build hit -- every link drew as its brackets. A link the page has no target for goes through
  `/link?title=`, resolved on the tap.
- `uv run pytest -q`: **328 passed, 8 deselected** (315 plus 13 in `test_links.py`: acceptance
  1, 3, 4 and 5, suggest and resolve, the rebuild, and two from review); `ruff` clean; schema
  asserts moved to 20.
- `npm run ui`: **17/17**, two new: S33 render (href to the target, missing dimmed, link at
  5.63:1, tap navigates without opening the editor, target lists the source) and S33 picker
  (offered with its space, inserted, autosaved). `tsc` clean.
- Looked at on 390px and 1280px: links, the dimmed missing link, "Linked from", and the picker,
  restyled from CodeMirror's default blue list to the app's panel with 44px rows.
- **Review** (a separate agent, backend only): one confirmed defect, fixed with a test -- the
  rewrite read every linking item's text before its loop, so a nested rewrite (B's first line
  links to A; C links to B and A) was overwritten by the stale copy, leaving C's link dead
  depending on row order. Also taken: no rewrite to a title whose own `[[…]]` would not key back
  to it (`**# odd**`).
- **Known gaps, accepted for now**, from the review: the server's `LINK` and marked disagree on a
  lone ```` ``` ```` mid-line, a code span across a line break, an escaped `\[[X]]`, and indented
  code; an item's link to itself is not renamed; a rename onto a title another item already has
  hands its links to whichever was touched last; past three levels of nested retitling the rest
  dims, unlogged; a rewritten item's text is trimmed of outer whitespace (`_clean`). On a phone
  the picker can reach the screen's right edge.

## Proof: phase B (2026-09-22, local)

- As built: `[[space:name]]` is the same token, keyed `space:name`; `store.space_of` reads it and
  `resolve_link` never answers one with an item. `GET /api/items/{id}` adds `space_links`
  (as written, to the space or null); `GET /api/spaces/{name}/linked` lists items elsewhere that
  link to the space. `rename_space` calls `store.rewrite_space_links` before its commit. The
  client draws a space link by the space's name, dimmed when the space is gone; the picker offers
  spaces after `[[space:`. "Linked here" sits under the space's list.
- `uv run pytest -q`: **332 passed, 8 deselected** (four more in `test_links.py`: acceptance 6
  and 7, a missing space, and a space link never opening an item); `ruff` clean.
- `npm run ui`: **18/18**, one new: S33 space link (drawn by name, opens the space, the item under
  Linked here, no sideways scroll). `tsc` clean.
- Looked at on 390px and 1280px: the space link and a dimmed missing one, the space picker, and
  Linked here on both layouts.
- No separate review for B: it reuses A's reviewed rewrite path (`relink`, `update_fields`).
