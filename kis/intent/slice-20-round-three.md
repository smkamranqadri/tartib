# Slice 20: round three (approved 2026-09-19)

Eight steps from the backlog, each proved on its own and committed on its own. One slice by the
user's choice, over a proposed split into two. Phase mode. No deploy in this slice.

Decided while planning:
- "Tell it why" follows the normal filing rules: a confident re-run files itself (the user's
  choice over "always back to you"). The reason is stored on the item, so a second wrong answer
  is at least traceable.
- Thought entries are read everywhere: search, Ask and the space brief.
- "Add directly" lives on the space page; the capture box stays AI-only.
- The session card is red -- a new `session` token in both themes -- replacing slice 19's teal.

## Step 1 — skeleton rows

Cards show grey rows in the shape of their content while loading, instead of a bare `...` and a
jump when data lands. Proof: browser with the API slowed, rows hold the layout.

## Step 2 — add a task or note directly

"+ Add" at the right of a space's title: task or note, the text, a due date for tasks. Files into
that space with no AI call. Stored as a capture with `source = 'direct'`, status done, so every
item keeps a capture and nothing in the schema changes. Proof: tests (filed item, no classifier
call, capture marked direct); browser.

## Step 3 — a filing policy per space

`spaces.policy`: `auto` (the global threshold), `ask` (always wait), `file` (always file when the
proposal names this space). Migration 0011. The runner applies it, as does step 7's re-run. Set
from the space page's "...". A rule the database and runner enforce, not a prompt line. Proof:
tests for all three against high and low confidence; browser.

## Step 4 — search lands on the line

A search result opens `/items/{id}?q=...`; the item page scrolls to the first match and marks
every match. Proof: browser with a long note.

## Step 5 — a session card

The slim bar becomes a card: a countdown ring and the controls while running, and the last two or
three sessions once stopped. A space's page lists that space's sessions. Colour: a red `session`
token in both themes. Rule 4 is rewritten as approved on 2026-09-19 -- a space may list its own
sessions; charts, streaks, cycles and long-break logic stay banned. Proof: browser, running and
done, light and dark; space page list.

## Step 6 — the space page split view

From 1100px, the list on the left and the open item on the right; a row click swaps the item
without leaving the page. The Tasks/Notes collapse state survives; `/items/{id}` links keep
working; phones unchanged. Proof: browser at 1280px and 390px.

## Step 7 — tell it why, instead of rejecting it

Replaces Reject. A sentence from the user re-runs the classifier on that item's text with the
reason as extra context. The new proposal follows the normal rules and the space's policy. The
reason is stored as `items.feedback` (migration 0012); the raw text is never rewritten (rule 1).
Rule 8 is rewritten when this lands. One AI call per disagreement. Proof: tests with the fake
CLI; eval fixtures that a reason moves the answer the right way.

## Step 8 — a thought section

An append-only log of dated entries on each item, the count on its rows. New `item_thoughts`
table with its own FTS5 index (migration 0013). Search, Ask and the space brief read the
entries. Proof: tests (append-only, search hit, Ask and brief context); browser.

## Out of scope

Slices 13 and 14, a classifier-proposed space, AI usage, photo and voice, offline, the deploy
and backups.
