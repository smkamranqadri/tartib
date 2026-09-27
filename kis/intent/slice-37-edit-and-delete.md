# Slice 37: editing and deleting, over MCP and in the thought log

Planned 2026-09-27 with the owner. Standard mode.
**Built and verified 2026-09-27 (Proof, below); deployed as `v2.4` the same day.**

## What was asked

The owner, in their words: "add note edit, thought edit, and delete for both in mcp".

## Decided with the owner, 2026-09-27

This reverses two earlier decisions: slice 35 offered editing text and deleting to agents and
the owner chose neither, and slice 20 made the thought log append-only (migration 0014's trigger).

1. **Thoughts become editable and deletable everywhere**: in the app and over MCP, so there is
   one rule. The append-only trigger goes. An edited thought is marked `edited_at` and says
   "edited", because the log was trusted as written until now.
2. **Items: notes and tasks alike**, like the app: `edit_item` changes an item's text,
   `delete_item` removes it. Delete removes the item only; its capture stays (rule 8).
3. **A text edit needs the `updated_at` the agent read** (from `get_item`). If the item has
   changed since, the edit is refused and the agent is told to read it again, the same check as
   the app's 409. A thought has no such guard: it is short, and only one person writes it.

## Challenges raised

- **Agents write unattended**, and slice 35 leaned on "nothing can be destroyed" for that.
  An item delete still keeps its capture, but a deleted thought is gone. The server's
  instructions say to edit or delete only when the person asks.
- **The thought count** was kept by an insert trigger alone, so a delete needs its own trigger,
  and the search index needs an update trigger.
- **Offline**: adding a thought queues offline (slice 25); editing and deleting one does not.
  It needs the network, and it says so when there is none.

## Build

- Migration 0024: drop `item_thoughts_append_only`; add `item_thoughts.edited_at`; an FTS
  update trigger; a count trigger on delete.
- `store.edit_thought`, `store.delete_thought`; `PATCH` and `DELETE
  /api/items/{id}/thoughts/{thought_id}`.
- MCP: `get_item` returns each thought's `id` and `edited_at`; new tools `edit_item(id, text,
  updated_at)`, `delete_item(id)`, `edit_thought(id, thought_id, text)`,
  `delete_thought(id, thought_id)`. Instructions updated.
- App: each thought has Edit and Delete (inline confirm), and shows "edited".

## Acceptance

1. `tools/list` shows fifteen tools.
2. `edit_item` with the current `updated_at` changes the text, and titles and links follow as in
   the app. With a stale one it is refused, and the text is unchanged.
3. `delete_item` removes the item, and its capture stays.
4. `edit_thought` changes the body, sets `edited_at`, and search finds the new words and not the
   old ones. `delete_thought` removes it and the count drops. A thought id from another item is
   refused.
5. In the app, a thought can be edited and deleted, and the count follows.

## Verification

`pytest` (migration, REST, MCP); `npm run ui` plus one check for the thought edit and delete;
`tsc`.

## Proof (2026-09-27, local)

- `uv run pytest -q`: **376 passed, 9 deselected**; `ruff` clean; schema asserts to 24. New:
  `test_thoughts.py` (an edit marks it, search follows the new words and forgets the old ones,
  `updated_at` stays; a delete drops the count and the index; a thought reached through another
  item is 404) and `test_mcp.py` (fifteen tools and the instruction; a stale `updated_at` refused
  and the text unchanged, the same one refused a second time; a task edit retitles it; delete
  keeps the capture; thought edit and delete, and one from another item refused).
- `npm run ui`: **22/22** on the rebuilt image, the new S37 check editing and deleting a thought
  through the UI. `tsc` clean. Looked at on 390px: "edited" beside the age, Edit and Delete muted
  at 44px targets, the edit box with Cancel and Save.
- Not done: a real client (Claude Code) against the local `/mcp`, and the phone.
