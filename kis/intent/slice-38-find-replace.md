# Slice 38: find and replace over MCP

Planned 2026-10-06 with the owner. Standard mode. Scope approved.
Review revisions verified locally 2026-10-06; merged into main at `b230c3d` on
2026-10-07 by fast-forward (same verified code tree). Deployed as v2.6 on 2026-10-07.

## Decided with the owner

- Add an MCP tool operating on one item per call.
- Match case-sensitive literal text and replace all matches.
- By default search the item's text and all its attached thoughts. The original capture is
  left unchanged.
- Apply immediately when called. Return only the id, updated_at, separate replacement counts
  and changed lines.
- Review revision: optional non-negative `expected` must equal the total matches before any
  writes. Optional `scope` is text, thoughts or both (default both). Preserve literal whitespace.
  The item timestamp does not detect thought edits; use current thought bodies under the lock.
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

## Review acceptance

- A seven-rule marker match with expected=1 refuses without changing any body or timestamp.
- Count spans the selected scope; text-only and thoughts-only edits leave the other untouched.
- Compact replies include changed line numbers and before/after lines, without unchanged text.
- Preserve outer whitespace and handle multiline insertion/deletion, including no-op calls.
- Revert the unrelated add-path reflow.

## Acceptance

1. `tools/list` includes `find_replace` and describes its scope and explicit-use rule.
2. Case-sensitive literal matches are replaced everywhere in one item's text and thoughts only;
   the tool returns counts and changed lines without echoing the item or unchanged thoughts.
3. Updated thoughts have `edited_at`; search finds the replacement and no longer finds the old
   thought text.
4. Replacing line one of a task updates its title and links through the normal item edit path.
5. Stale `updated_at` is refused before writes; no matches leave the item and thoughts untouched.
   Empty search, blank bodies, and text beyond the existing limit are refused without partial
   writes.

## Baseline verification (before review revisions)

- `cd backend && UV_CACHE_DIR=/tmp/tartib-uv-cache uv run pytest -q`: **381 passed, 9 deselected**.
- `cd backend && UV_CACHE_DIR=/tmp/tartib-uv-cache uv run ruff check tartib/mcp_server.py tests/test_mcp.py`:
  passed.
- `git diff --check`: passed.
- Mutation checks: empty search, stale item version, blank item result, blank thought result, and
  item/thought size limits each failed their focused test when disabled; the source was restored
  byte-for-byte from the saved original after each mutation.


## Review verification

- Backend suite: **383 passed, 9 deselected**, one existing Starlette deprecation warning.
- Five focused find/replace tests pass, including count mismatch with unchanged bodies and
  timestamps, scope isolation, current thought bodies, whitespace and multiline insertion.
- Single-rule response is under 500 characters for a roughly 10,000-character note.
- Eight guard mutations (expected count, negative expected, empty search, stale timestamp,
  blank item/thought and item/thought limits) each fail their targeted test. Restored source
  byte-for-byte before the backend suite.
- Ruff on the three changed Python files and `git diff --check` pass.
- Compared against main: the unrelated insert_item reflow is removed.

- Final description and server instruction use the owner's exact wording (2026-10-07).

- v2.6 live verification (2026-10-07): running image confirmed, health ok with AI on,
  17 MCP tools, exact tool description and expected/scope schema. Count mismatch refused;
  independent get_item readback unchanged. Successful production replacement not exercised.
