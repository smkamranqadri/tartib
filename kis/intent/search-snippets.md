# The MCP search returns summaries, not whole items (2026-10-09)

Owner-directed context fix, Standard mode on `search-snippets` from the orchestrator brief
`orch-skill/.orch/tartib-search/brief.md`. It answers findings cause 1: a fuzzy MCP `search`
returned the full text of every hit (22k–35k chars per call), and `list_items` returned a whole
space (93k), so agents paid for each note about three times. Shared State belongs to the
coordinator and is not changed by this stream.

## Cause

`_item()` in `mcp_server.py` put `serialize_item(row)["raw_text"]` into every hit's `text`, and
both `search` (up to `MAX_ITEMS = 20`) and `list_items` (up to `LIST_LIMIT = 100`) used it. The
tools that list items are the ones an agent calls first, so the whole text of the space arrived
before any reads.

## The fix

`search` and `list_items` now return a **summary per item**, and `get_item` stays the only way to
read one in full:

- `mcp_server._hit(row)`: id, space, shape, title, due, remind_at, starred, status, stage,
  created_at, updated_at, thought_count, plus `first_line` (from the text — a note keeps no
  `title`, so this is what names it) and `snippet`. No `text`.
- `store.search()` selects `snippet(items_fts, -1, '[', ']', '…', 12) AS snippet`; for a hit
  found only through a thought, `items_by_thoughts()` selects the matched thought's own
  `snippet(thoughts_fts, …)`. Both are ignored by the other callers (`ask.py`, `similar_items`).
- `list_items` has no query, so its `snippet` is a short opening excerpt (200 chars).
- The two tool descriptions and the server `INSTRUCTIONS` say results are summaries and
  `get_item` reads a whole item.

Decisions (the owner's): `list_items` trims too; the replies that echo one item just written
(`add_*`, `edit_item`, `set_*`) stay full; REST (`/api/items?q=`) and the app's own search are
**unchanged**; the lore mapping is flagged, not edited (it lives outside this repo).

## Proof (2026-10-09)

- Measured on a throwaway database shaped like the ai-agents space (30 items, one ~40k note;
  `measure.py`, sizes are the JSON item payload of one call):
  - `search`: **32,154 → 6,734 chars** (4.8×).
  - `list_items`: **87,520 → 15,016 chars** (5.8×).
  - `get_item` unchanged: 1,622 chars for the same item.
- `cd backend && uv run pytest -q` → **399 passed, 10 deselected** (397 + 2 new), ruff clean.
- New guards in `tests/test_mcp.py`, each mutation-checked (break, see it fail, restore the saved
  original byte-for-byte):
  - `test_search_and_list_items_return_summaries_not_whole_items` — no `text` key, `first_line`
    and `snippet` correct, whole reply < 2,000 chars where the bodies are 30k+. Mutations: `_hit`
    returning `_item` fails it; the snippet falling back to the raw text fails it (size).
  - `test_a_hit_found_through_a_thought_shows_the_thought` — a thought-only hit's snippet holds
    the matched word. Mutation: dropping the `items_by_thoughts` snippet subquery fails it.

## Callers

- `INSTRUCTIONS` updated in the same change.
- **lore** (`~/.agents/skills/lore/backends/tartib.md` line 40) matches a search hit's first line
  then `get_item`s to read; `first_line` in the hit keeps it working, and its line should name
  `first_line`. The user updates that file — it is outside this repo.
- `~/.agents/skills/tartib/SKILL.md` (lines 17, 34, 39) describes `search` and `list_items` as
  returning items; it has no repo source, so the user updates it too.

## Status

Implemented on `search-snippets`, uncommitted. No migration, no frontend change, not deployed.
