# Slice 20: round three (approved 2026-09-19)

**All eight steps done and proved locally, 2026-09-19; not deployed.** Open until the user has
tried it. Migrations 0011-0014. Rules 4 and 8 rewritten.

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

**Done 2026-09-19.** `Loading` in `Status.tsx` now renders grey rows (title and meta bars, varied
widths, a gentle pulse that stops under reduced motion) instead of "Loading...". Added where a
card showed nothing while loading: Home's Needs attention and Recent, the space page's Tasks and
Notes, and the item page. Settings' inline "..." values are left as they are -- single values,
not rows. Proof: headless Chrome at 390px with every `/api/` response held 2 s: skeletons on
Home (3 cards), a space (2) and an item (1) while loading, none after. Typecheck and build pass.

Cards show grey rows in the shape of their content while loading, instead of a bare `...` and a
jump when data lands. Proof: browser with the API slowed, rows hold the layout.

## Step 2 — add a task or note directly

**Done 2026-09-19.** One correction to the plan: `captures.source` is a CHECK constraint (`web`,
`api`, `migrated`), so `'direct'` is not a value it can take without rebuilding a table `items`
references. A column instead: `captures.direct` (migration 0011), with `source='web'`,
`status='done'`. This moves the later migrations up one: policy 0012, feedback 0013, thoughts
0014. `POST /api/items {shape, space, text, due?}`; an unknown space is 422 and leaves no capture
behind; a note drops any due date. `reclassify` skips `direct=1` in both scopes -- without that,
`--all` would hand a hand-filed task to the model. Proof: `tests/test_direct.py`, 4 tests (filed
with no classifier call, recorded by the fake CLI; note drops due; unknown space rolled back;
reclassify skips it); pytest 173 passed, ruff clean. Headless Chrome at 390px and 1280px: "+
Add" -> task with a due date lands in Tasks with "Sep 25", Note hides the date and lands in Notes,
the form closes, no horizontal overflow.

"+ Add" at the right of a space's title: task or note, the text, a due date for tasks. Files into
that space with no AI call. Stored as a capture with `source = 'direct'`, status done, so every
item keeps a capture and nothing in the schema changes. Proof: tests (filed item, no classifier
call, capture marked direct); browser.

## Step 3 — a filing policy per space

**Done 2026-09-19.** Migration 0012 (not 0011, see step 2). `store.should_file` is the one rule;
the runner calls it per proposal with the spaces' policies read once per capture. `GET
/api/spaces` gained `policies`; `PUT /api/spaces/{name}/policy`. The space page's "..." lists
"Files when sure", "Always ask me", "Always file here" with a tick on the current one, and the
subtitle says so when it is not the default. Three existing tests compared the whole `/api/spaces`
body and now compare its `spaces` list. Proof: `tests/test_policy.py` -- the rule table, no space
never files, the runner filing and holding by policy through the fake CLI, and the API (listed,
set, kept across a rename, 404, 422); pytest 180 passed, ruff clean. Headless Chrome at 390px: the
menu sets and ticks each policy, the server stores it, and the subtitle line matches.

`spaces.policy`: `auto` (the global threshold), `ask` (always wait), `file` (always file when the
proposal names this space). Migration 0011. The runner applies it, as does step 7's re-run. Set
from the space page's "...". A rule the database and runner enforce, not a prompt line. Proof:
tests for all three against high and low confidence; browser.

## Step 4 — search lands on the line

**Done 2026-09-19.** Marked in the browser rather than by FTS5's `highlight()`: the item page
already has the text, and the terms come from the query, so no API field was needed. `Highlight`
marks every term case-insensitively and by prefix, matching how the server searches. Rows from a
search (Spaces results, a space page with a query) link to `/items/{id}?q=...`; the item page
scrolls the first mark to the centre. Proof: headless Chrome at 390px, an 89-line note with the
match on line 60: searching "boiler press" on Spaces links with `?q=boiler%20press`, the page
opens scrolled (scrollY 3307) with "boiler" and "press" marked and the first in view; the same
item opened without `q` marks nothing and stays at the top. Typecheck and build pass.

A search result opens `/items/{id}?q=...`; the item page scrolls to the first match and marks
every match. Proof: browser with a long note.

## Step 5 — a session card

**Done 2026-09-19.** `GET /api/sessions/recent?space=&limit=` -- finished sessions, newest first,
with the item's title, text and space. The card (still `SessionBar.tsx`) is red from a
`--session` token (#d6453d light, #ff7b6b dark): a 48px ring emptying clockwise while running,
and once stopped the outcome buttons with the three sessions before this one, one line each
("Fix gate · 25 min · done · 2h ago"). A space page gets a Sessions card of its last 20, only
when it has any, and not while searching. Rule 4 rewritten. While building, a script truncated
`SessionBar.tsx` (opened for write before reading it); restored from git and redone, nothing
committed in between. Proof: new test for `/sessions/recent` (a running session is excluded,
newest first, titles joined, scoped by space); pytest 181 passed. Headless Chrome at 390px:
running card in light and dark with the ring's offset growing; after a stop the card shows the
three earlier sessions and not the one being asked about; home lists its sessions, work (none)
shows no card. Typecheck and build pass.

The slim bar becomes a card: a countdown ring and the controls while running, and the last two or
three sessions once stopped. A space's page lists that space's sessions. Colour: a red `session`
token in both themes. Rule 4 is rewritten as approved on 2026-09-19 -- a space may list its own
sessions; charts, streaks, cycles and long-break logic stay banned. Proof: browser, running and
done, light and dark; space page list.

Moved after a look on the device, same day: the card left the top of every page for its foot,
`position: sticky` just above the ask bar -- whose height the bar publishes as `--askbar-h`
through a ResizeObserver, since it grows with an answer and wraps on a phone -- or above the
screen edge where there is none. Proof: headless Chrome with a session running, Home at 390px
and 1280px, a space and Recent at 390px: the card is in view at the top and at the end of each
page and always clears the ask bar.

Then, same day: one behaviour everywhere -- the ask bar is on every page, not only Home and the
Inbox, with the session card held just above it; the split view's pane now also leaves room for
the bar. Proof: headless Chrome with a session running, seven pages (Home, Inbox, Recent, Spaces,
a space with an item open, an item, Settings) at 390px and 1280px, at the top and the end of
each: the ask bar in view, the card above it and in view, no horizontal overflow.

And: with no session running the card no longer disappears. It stays, quiet (panel colours, a
small empty ring): "No session running", Start for a fresh one, and the last three sessions each
with ▶ to run the same task again. Proof: headless Chrome at 390px after closing the running
session: the idle card lists three with ▶; ▶ on a task's row started a running session on that
task and the card turned red with its countdown.

## Step 6 — the space page split view

**Done 2026-09-19.** `useWide(1100)`; on a wide screen `Space.tsx` renders the list and an
`<aside>` holding `ItemPage` embedded (`itemId` given: no Back link, `onChanged` bumps the list's
version, delete clears `?item`). The open item is `?item={id}` in the URL, carrying `q` when
opened from a search. `ItemRow` gained a `to` override; `SpaceDetail` a `rowTo`. The pane is
sticky and scrolls on its own. Proof: headless Chrome at 1280px: an empty pane says "Pick an
item", a row click sets `?item=7` and shows it with the list still there, a second swaps to
`?item=6`, Back returns to 7; Notes collapsed stays collapsed after opening an item; starring
in the pane stars the row in the list; no horizontal overflow. At 390px no split, rows link to
`/items/{id}`. Typecheck and build pass.

From 1100px, the list on the left and the open item on the right; a row click swaps the item
without leaving the page. The Tasks/Notes collapse state survives; `/items/{id}` links keep
working; phones unchanged. Proof: browser at 1280px and 390px.

## Step 7 — tell it why, instead of rejecting it

**Done 2026-09-19.** `POST /api/items/{id}/redo {reason}` replaces `/reject`, which is gone
(404/405). The reason is normalised, appended to `items.feedback` as "YYYY-MM-DD: reason" and
committed before the AI call. `classify` takes `correction=(earlier proposal JSON, reason)`,
placed just above the text, restating that a space must be an existing one. The first
non-question proposal replaces the item's fields and proposal; `should_file` (so the space's
policy too) decides filed or still waiting. The card's "..." says "Tell it why..." -- a one-line
reason with Try again; the Approve row hides meanwhile, and Enter in the reason is not an
approval. Rule 8 rewritten. Proof: `tests/test_redo.py`, 6 tests (confident re-run files, with
the reason and earlier proposal in the recorded prompt and the text still last; unsure stays
waiting; the `ask` policy holds; reasons accumulate and survive a 502; 422/409 refusals; reject
is gone), the old reject test removed; pytest 186 passed; ruff clean. Real-Codex eval: 3 new
cases (note to task and work to home; finance to home; task to note keeping its space) and the
22 existing ones passed on the first run. A second run could not reach the model: the Codex
usage limit hit ("try again at Sep 20th, 2026 1:51 AM"), so it is one clean run, not two.
Headless Chrome with the fake CLI: "Tell it why..." -> reason -> Enter filed the item to home,
the card left the list, the reason was stored.

Replaces Reject. A sentence from the user re-runs the classifier on that item's text with the
reason as extra context. The new proposal follows the normal rules and the space's policy. The
reason is stored as `items.feedback` (migration 0012); the raw text is never rewritten (rule 1).
Rule 8 is rewritten when this lands. One AI call per disagreement. Proof: tests with the fake
CLI; eval fixtures that a reason moves the answer the right way.

## Step 8 — a thought section

**Done 2026-09-19.** Migration 0014 (0013 in the plan, see step 2): `item_thoughts`, append-only
by trigger, cascading with its item, `thoughts_fts` for search, `items.thought_count` by trigger.
One thing the plan did not foresee: the count is an update of `items`, and the touch trigger would
have moved `updated_at` on every thought -- so an editor open beside the log would be refused as
stale on its next save. The trigger is narrowed to skip `thought_count`, as 0005 did for
`reminded_at`. Search and Ask add items matched only by their thoughts after the ones their own
text matched; Ask and the brief see each item's thoughts under it; a new thought refreshes the
brief. Item page: a Thoughts card, oldest first, add box; rows show "2 thoughts". Proof:
`tests/test_thoughts.py`, 7 tests (append and count, rewrite refused, `updated_at` unmoved and a
stale-checked save still lands, search order, Ask prompt carries the thought, brief regenerated
and reading it, cascade on delete); pytest 193 passed, ruff clean. Headless Chrome at 390px: two
thoughts added and listed, the row says "2 thoughts", searching "Aldi" (only in a thought) finds
the item. Typecheck and build pass.

An append-only log of dated entries on each item, the count on its rows. New `item_thoughts`
table with its own FTS5 index (migration 0013). Search, Ask and the space brief read the
entries. Proof: tests (append-only, search hit, Ask and brief context); browser.

## Out of scope

Slices 13 and 14, a classifier-proposed space, AI usage, photo and voice, offline, the deploy
and backups.
