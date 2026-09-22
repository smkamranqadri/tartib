# Slice 34: suggest links for items already filed

Planned 2026-09-22 with the owner, after a dry run of slice 33 phase C on 15 `infra` notes from a
live snapshot proposed about 11 good links (the CapRover -> Docker -> Server chain among them) and
wrote nothing. Phase C only proposes links for new captures; this is the pass for what is already
filed. Standard mode.
**Built and verified 2026-09-23 (Proof, below); not deployed.**

## Decided with the owner, 2026-09-22

1. **A command on the server**, not a button: `python -m tartib.suggest_links --space NAME
   [--limit 20] [--dry-run]`. `--space` is required and `--limit` defaults to 20, so one run is
   about 20 calls; no `--all`. Offered a button on the space page.
2. **Notes and tasks**, every filed item in the space. Offered notes only.
3. **Each item's own context**: the similar items a new capture would be shown, minus itself,
   asked for links whatever `TARTIB_LINK_PROPOSALS` says -- running the command is the ask.
   Recorded in `ai_calls` as kind `relink`, `links_on` = 1.
4. **One link per pair**: when A and B propose each other only one suggestion is kept, and pairs
   already linked either way are skipped.
5. **A skipped pair is never proposed again**; items already carrying links are still checked
   for more.
6. **Review in Needs attention, the item back to waiting** (reason `relink`), keep or drop each
   link as a chip, approve appends `Related: [[…]]`. Offered keeping the item filed with a card of
   its own; the owner chose waiting, with the guards below.

## Challenge, and the guards the owner accepted

Waiting has meant "a capture not filed yet", and several things read it that way. So:

- **Suggestions live in their own table**, never in `proposal_json`: the classifier learns from
  the gap between its proposal and what was filed (`classifier_examples`), and overwriting it
  would corrupt that.
- **Approve on a `relink` item files it back exactly as it is** -- its current space, title, due
  -- where an ordinary approve re-applies the stored proposal and would undo edits made since.
- **`classified_at` is not touched**, so a refiled item is not a fresh example.
- **The `relink` card offers the chips, Approve and Not now only**; "Tell it why" would reclassify
  an old item from scratch.

Accepted: a waiting task is off Today until answered, and one run can put 20 items in the inbox.
If that proves too much, the stay-filed card can replace waiting later; the table carries over.

## Build

- Migration 0022: `link_suggestions(item_id, target_id, state pending|kept|skipped, created_at)`,
  both ids cascading on delete, unique per pair.
- `tartib/suggest_links.py`: the CLI; 3 calls at a time; `--dry-run` prints and stores nothing.
  Candidates and resolution reuse `similar_items`, `Context(links=True)` and `_resolve_related`.
- A run stores pending suggestions and moves each item that got one to `stage = 'attention'`,
  `wait_reason = 'relink'`, leaving every other field alone.
- `/api/attention`: `related` for `relink` items from the pending suggestions.
- Approve for `relink`: keeps the item's own fields, appends the kept links, marks kept and
  skipped, back to `filed`. Not now leaves it waiting.
- Card: no "Tell it why" on `relink`; the reason line says what it is.

## Out of scope

A button in the app; `--all`; reviewing without unfiling; adjusting tasks' due dates.

## Acceptance

1. `--dry-run` prints and writes nothing (row counts and `ai_calls` unchanged).
2. A run stores suggestions and sends only those items to waiting as `relink`; one per pair; none
   for pairs already linked or skipped before; `--space` required; `--limit` respected.
3. Approve: kept chips become a `Related:` line; the item is filed back with its own space, title
   and due; `classified_at` and `proposal_json` unchanged; a dropped chip is marked skipped and
   never proposed again.
4. A `relink` card has no "Tell it why".

## Verification

- `pytest` with a new `test_suggest_links.py` on the fake model.
- `npm run ui` plus one check for the `relink` card, stubbed at the network.
- One real run on a live snapshot, `--dry-run --space infra --limit 5` (5 calls), before any real
  run on the server.
- Review of the unfile and refile path before it ships: it changes filed items' stage.

## On ship

`technical.md`: the table, the `relink` reason and its approve rule, the CLI beside reclassify.
SPEC: the reason in Needs attention. history.md.

## Proof (2026-09-23, local)

- As built: migration 0022 (`link_suggestions`, and `link_asks` added after review);
  `tartib/suggest_links.py`; `store.suggest`, `pending_suggestions`, `pair_known`,
  `refile_relinked`, `WAIT_RELINK`; approve and redo branches in `items.py`; `reclassify
  --attention` skips `relink`; the card and the item page's form start from the item for `relink`,
  and neither offers "Tell it why".
- `uv run pytest -q`: **351 passed, 9 deselected** (eleven in `test_suggest_links.py`: acceptance
  1 to 4 -- dry run stores nothing, one per pair, filed back with its own space and due and
  `classified_at`/`proposal_json` unchanged, a skipped pair never again, redo refused and
  reclassify skipping -- plus an existing link counting as the pair, limit and unknown space, an
  invented label, and three from review); schema asserts to 22; `ruff` clean.
- `npm run ui`: **20/20**, one new: S34, the `relink` card stubbed with a proposal naming another
  space -- it sends the item's own space, no "Tell it why". The item page's "File it" checked the
  same way in a scratch script: it shows and sends `coding`, the item's, not `games`, the
  proposal's. `tsc` clean.
- **Live snapshot, `--dry-run --space infra --limit 5`** (2026-09-23): migrated the copy to 22
  and indexed 196 items; 5 calls, 61s; 4 items would be sent back with 6 links (#212 Ubuntu,
  #211 Server Setup and Docker -- the pair with #212 not offered twice --, #210 Server Setup,
  #204 the AWS exam article and, weakly, Mongodb Cluster Operations); nothing stored, no
  `ai_calls` rows. The snapshot was deleted after, here and on the host.
- **Review** (a separate agent): three confirmed and fixed with tests -- the item page's "File it"
  re-applied the first proposal (an item moved since would be moved back); a task's pending
  reminder would be written off while it waited (such tasks are now skipped); an item or target
  deleted mid-run crashed the command on a foreign key (`suggest` now re-checks). Also taken: an
  item that got nothing was asked again on every run (`link_asks`). Accepted as known: the touch
  trigger moves `updated_at` when an item is sent back and refiled, so it leaves the stale list;
  a kept `Related:` line is in the text the examples quote.
