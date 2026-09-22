# Slice 30: a split waits for you, and can be kept as one

Planned 2026-09-22, the day `v2.0` went live. Standard mode. On branch
`sc-superfluid-magnon-e253`, not `main`: another agent is working on `main`. Not deployed; the
owner decides when it merges.

## What happened

Checked on the live app 2026-09-22. Two pasted captures were split into pieces and **every piece
filed itself** at 0.97-0.99:

- **#92**, a heading "Personal Preferences For AI Agent" over 9 lines of preferences, a brand
  palette and a tagline, became 9 notes: 7 in `personal`, 2 in `personal-brand`. **The heading
  is in none of them.**
- **#91**, "prompts\n❯ add smooth scrolling, subtle hover effects on links, and a nice fade in
  animation when the page load", became 3 tasks in `coding`. "prompts" was dropped.

The owner meant both as single notes. Both are prompts to keep.

**Cause:** the prompt (`classify.py`, the paragraph after the reply format) says to split "when
the text lists distinct actions or facts ("A, B, and C", bullets, separate lines)". A heading
over lines looks like a list of facts. Each proposal keeps only its own slice of the text, so a
heading line that belongs to all of them ends up in none.

**Nothing is lost.** The capture's `raw_text` is immutable and still whole. Repairing the two
live captures is a separate job and is not part of this slice.

## Decided with the owner, 2026-09-22

1. **A capture that splits into more than one item never files any of them.** This holds whatever
   the confidence and whatever the space's filing policy. Each piece waits in Needs attention with
   a new wait reason, `split`.
2. **"Keep as one"** on a split card replaces all of that capture's pieces with one note, built
   from the capture's `raw_text`. The owner then files that note like any other waiting item.
3. **The prompt is fixed as well.** A heading followed by lines that belong under it is one note.
   Split only when the lines are separate things to do or facts that have nothing to do with each
   other.

Rule 1 is the safety net and rule 3 makes it rarely needed. Rule 1 catches every split, including
the ones the prompt gets wrong later.

## Decided in this plan (confirmed by the owner, 2026-09-22)

- **What counts as a split:** more than one item that is *not a question*. A capture holding one
  task and one question makes one item plus an answer. That is not a split, and it behaves as it
  does today.
- **Precedence:** `split` comes first in `wait_reason_for`, ahead of `duplicate` and `asked`.
  Reason: it is a decision about the whole capture, and Keep as one makes the others moot. If a
  piece asked a question, its answer buttons still show, because the card reads
  `proposal.clarify` as well as the reason.
- **Keep as one works only while every remaining piece is untouched**, in the same spirit as the
  retry rule. For each piece that means: still waiting, still `split`, no thoughts, no "tell it
  why" reason, and never edited. Approving one piece, answering its question, tapping a word in its
  sentence or redoing it counts as starting on it. After that, the button disappears from all of
  that capture's cards. The server refuses the merge with 409 if it is asked anyway.
  - **How "never edited" is detected, with no migration:** `insert_item` writes `updated_at` from
    the same timestamp as `classified_at`. An edit that passes through the touch trigger moves
    `updated_at`, so "untouched" means `updated_at = classified_at`. Today the insert trigger sets
    `updated_at` separately, a moment later.
  - **Deleting a piece does not block the merge.** Deleting it is not starting on what remains,
    and Keep as one promises the whole original text. So the deleted words come back inside the
    merged note. The button's tooltip says so ("one note holding the original text, whole"). The alternative
    would be recording N on each piece, which needs a column, for an edge case that is itself a
    choice to discard.
- **The merged note's space:** if every piece proposed the same space, the merged note proposes it.
  #91 comes back as a note in `coding`. If the pieces disagree, the note has no space and carries
  the classifier-asks question: "Where does this go?", with the pieces' distinct spaces as buttons
  (2 to 6, dropped when there are more than 6). #92 would offer `personal` and `personal-brand`.
  This reuses slice 27's UI and adds no new UI.
  - It is always a **note**, never a task: tasks cannot be merged sensibly, and one tap turns it
    into a task.
  - Its reason is a second new code, `whole`, and the card shows "Kept as one: choose where it
    goes". Without it, a merged note with a space would read "Unsure (N%)", which is wrong. Merged
    notes never file themselves either.
- **API:** `POST /api/captures/{id}/whole` returns the new item and deletes the pieces in one
  transaction. It takes the capture id, not an item id, because it acts on the capture. It works
  online only, like Approve.
- **The card:** a split piece shows "Split from one capture into N" and a **Keep as one** button
  beside Approve. `/api/attention` adds `split: {of: N, whole: bool}` to each `split` item, so the
  card knows N and whether the button is allowed, with no extra request.
- **`reclassify.py` inherits all of this**, because it goes through `Runner._apply`.

## Steps

1. **Store:** add `WAIT_SPLIT = "split"` and `WAIT_WHOLE = "whole"`, plus a `split` argument to
   `wait_reason_for`. Make `insert_item` set `updated_at = classified_at`.
2. **Runner `_apply`:** count the non-question proposals. If the count is 2 or more, every piece
   goes to `attention` with `split`.
3. **Keep as one:** a store function `keep_whole(conn, capture_id)` with the guard, the proposal
   built as above, the insert and the deletes, plus the route. `/attention` gains `split`.
4. **Prompt:** rewrite the split paragraph with a positive and a negative example. The heading case
   goes in, and "call Ali, buy milk" still splits. Keep it short: every capture pays for these
   tokens.
5. **Frontend:** `types.ts` (`split`), `format.ts` (`split` and `whole` wording),
   `ApprovalCard.tsx` (the line and the button), `api.ts` (`keepWhole`). After a merge the Inbox
   reloads, because N cards become one.
6. **Tests** (below), then SPEC and State via `/kis:sync`.

## Verification

- **Unit tests**, with the fake Codex:
  - a capture with 2+ proposals files none of them and every piece carries `split`, even at 0.99
    on a `file` policy space;
  - one proposal files as before;
  - one item plus a question is not a split;
  - Keep as one: one note, `raw_text` equal to the capture's text byte for byte, the pieces gone,
    the space proposed when the pieces agree and asked when they don't, reason `whole`, and
    approving it files it;
  - Keep as one is refused (409) after one piece is approved, edited or given a thought, and
    refused for a capture that did not split;
  - `/attention` reports `split.of` and `split.whole`.
  - The existing `test_multi_item_capture_splits_into_items` expects `filed, filed, attention`.
    It changes to all `attention`: that is the new rule working, not a regression.
- **One targeted eval**, `test_a_heading_stays_one_note`, run alone with
  `uv run pytest -m eval -k heading`: 4 captures, so 4 calls, run concurrently on the pinned
  `gpt-5.6-luna`. The whole suite is not run.
  - #91 verbatim → 1 proposal.
  - #92 → 1 proposal. **Reconstructed, not verbatim:** the same shape (a heading, 7 preference
    lines, a palette line and a tagline) with neutral wording. The real text is the owner's
    personal content and this repo is public. Neither session has the verbatim text either.
  - "call Ali, buy milk" → 2.
  - The existing bullets fixture ("- pay the electricity bill\n- book the car service\n- send the
    invoice to Ahmed") → 3. It guards the other direction: a list with no heading must still
    split.
  - Spaces for this test: the eval's six plus `personal` and `coding`.
  - A fast failure is rate-limiting (technical.md). Re-run once before believing it.
- **Full suite:** expect 286 passed plus the new tests, 7 deselected becoming 8 (the new eval),
  ruff clean, typecheck and build clean, `npm run ui` 10/10.
- **Browser, at phone width** (playwright-core, channel chrome; the extension is not connected
  here): a split capture shows N cards, each saying "Split from one capture into N". Keep as one
  leaves one card with the full text. Approving it files it. The fake Codex is driven locally;
  the live app is never touched.

## Risk

- **The prompt change could stop legitimate splits.** Seen from the other side, that is a capture
  kept whole that should have been two, and the owner can still split it by hand. Rule 1 means
  the opposite error never files itself any more. The eval's split cases (the bullets and "call
  Ali, buy milk") are the guard.
- **More waiting.** Every multi-item capture now costs the owner a tap per piece, or one Keep as
  one. That was the owner's choice: they would rather be asked.
- **`updated_at = classified_at` at insert** changes the timestamp every inserted item carries,
  by milliseconds and to second precision. The stale-save check compares for equality against
  what the client last saw, so it is unaffected. Stale compares against a cutoff 14 days old.
- **An inbox with open tabs:** a card can outlive a merge made in another tab. Approving a deleted
  piece returns 404, as approving any deleted item does today.

## KIS writes this implies

- Knowledge: none expected. A prompt lesson, if the eval teaches one, goes to technical.md.
- Intent: this file; SPEC (Classify: the split rule and the two new reasons; Needs Attention
  decisions: Keep as one; Screens, the Inbox card: the split line); history.md on close.
- State: the task in flight while it runs. On close, "on this branch, not merged, not deployed".

## What was built (2026-09-22) -- done and proved, on the branch, not merged

Built as planned; commit `1f24ea0`. One thing the plan got wrong, caught by an existing test:

- **`updated_at = classified_at` had to be in milliseconds.** The plan wrote both at second
  precision. `test_today_reports_active_space` failed, because `updated_at` is compared as a
  string and `…:00Z` sorts *after* `…:00.100Z` from the same second, so a piece written this
  second looked newer than an edit made a moment later. Both are now one `utcnow_ms_iso()`.
  The plan's Risk line claimed the change was harmless; it was not, and the test said so.
- A **session** on a piece also counts as starting on it. Not in the plan: `sessions.item_id` is
  `ON DELETE SET NULL`, so deleting that piece would have cut the session off from its task.
- Two existing tests assumed a split files its confident pieces: `test_multi_item_capture_
  splits_into_items` now expects every piece waiting, and `test_recent_page_leaves_out_what_is_
  waiting` reaches its "one filed, one waiting" state by approving one piece.

## Verification -- what actually ran

- `uv run pytest -q`: **299 passed, 8 deselected** (286 before, plus 13 in `test_split.py`;
  the eighth deselected is the new eval). `ruff check` clean. `npm run typecheck` and
  `npm run build` clean.
- **The one targeted eval**, `pytest -m eval -k heading`, pinned `gpt-5.6-luna` at medium,
  passed first time: 4 calls, 27s. The preferences note came back as 1 note in `personal`, #91
  as 1 item in `coding` (a task, not a note -- shape is not asserted, and one tap changes it),
  "call Ali, buy milk" as 2, the bullets as 3. No baseline was measured for the old prompt: the
  live app is the evidence that it split both.
- `npm run ui`: **10/10**, against this branch's own server on port 8010 (a scratch database, the
  fake classifier). Port 8000 was left to the main checkout.
- **Browser at 390px** (playwright-core, channel chrome), 12 checks, all ok: a 3-way split shows
  3 cards, each "Split from one capture into 3" with Keep as one (44px, no horizontal scroll);
  Keep as one leaves one card with #91's text byte for byte, "Kept as one: choose where it goes",
  proposing `coding`; Approve files it there whole. Pieces in `personal` and `work` merge into a
  note asking between exactly those two. Approving one piece of a two-way split removes Keep as
  one from the other.

## Still open

- **The two live captures are not repaired.** Blocked twice by the permission check on bulk
  deletes on the live server; the owner's call. Keep as one cannot repair them after deploy:
  their pieces already filed themselves, and it only acts on waiting ones.
- Merge and deploy are the owner's decision.
