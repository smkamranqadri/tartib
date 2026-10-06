# Slice 38: find and replace over MCP

Planned 2026-10-06 with the owner. Standard mode. Scope approved.
Built and verified locally 2026-10-06; not deployed.

## Decided with the owner

- Add an MCP tool operating on one item per call.
- Match case-sensitive literal text and replace all matches.
- Search and replace in the item's text and all its attached thoughts. The original capture is
  left unchanged.
- Apply immediately when called. Return the updated item and separate replacement counts for
  item text and thoughts.
- Changed thoughts are marked edited, following the existing `edit_thought` behavior.

## Build

- Add `find_replace` to the MCP server and its instructions. Require `id`, `find`, `replace`, and
  the `updated_at` read from `get_item`; reject a stale item before writing.
- Apply item and thought updates atomically through existing store paths, preserving task title,
  link indexing, thought edit markers, and the FTS index.
- A missing match is a successful no-op with zero counts. An empty search string is refused.
  An empty replacement is allowed unless it would leave an affected item or thought blank; in
  that case the whole call is refused without changes. Existing 20,000-character limits still
  apply to edited item and thought text.
- Add MCP regression coverage for matching, counts, thought edit markers and FTS, task title
  updates, stale edits, and no-match behavior.

## Acceptance

1. `tools/list` includes `find_replace` and describes its scope and explicit-use rule.
2. Case-sensitive literal matches are replaced everywhere in one item's text and thoughts only;
   the tool returns the updated item and replacement counts.
3. Updated thoughts have `edited_at`; search finds the replacement and no longer finds the old
   thought text.
4. Replacing line one of a task updates its title and links through the normal item edit path.
5. Stale `updated_at` is refused before writes; no matches leave the item and thoughts untouched.
   Empty search, blank bodies, and text beyond the existing limit are refused without partial
   writes.

## Verification

- `cd backend && UV_CACHE_DIR=/tmp/tartib-uv-cache uv run pytest -q`: **381 passed, 9 deselected**.
- `cd backend && UV_CACHE_DIR=/tmp/tartib-uv-cache uv run ruff check tartib/mcp_server.py tests/test_mcp.py`:
  passed.
- `git diff --check`: passed.
- Mutation checks: empty search, stale item version, blank item result, blank thought result, and
  item/thought size limits each failed their focused test when disabled; the source was restored
  byte-for-byte from the saved original after each mutation.
