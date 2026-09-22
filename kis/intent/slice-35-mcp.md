# Slice 35: Tartib over MCP

Planned 2026-09-23 with the owner. Standard mode.

## What was asked

The owner, in their words: an MCP server "so you can connect easily and pull note or task and add
note or thought or task". Three uses named:

- in a project such as `namazee`, an agent pulls up that space's tasks, plans, and after the work
  is done updates Tartib -- the task done, a thought saying what happened;
- what was learned in a session goes in as a note in a learning space;
- what is worth sharing goes in as a note in `social-media`, which the owner later picks up in the
  social-media project to plan a post.

## Decided with the owner, 2026-09-23

1. **Inside Tartib, at `/mcp`**, over MCP's streamable HTTP, deployed with the app: one URL and a
   token from any machine. Offered a local stdio program per machine.
2. **Its own token**, `TARTIB_MCP_TOKEN`, not the login password; unset, `/mcp` is off.
3. **Read**: `list_spaces`; `list_items(space, shape?, status?)`, open tasks first;
   `search(query, space?)`; `get_item(id)` with its thoughts and links. **No Ask**: the agent
   reasons itself, so reading costs no quota.
4. **Write**: `add_note` / `add_task(text, space?, due?)` -- **filed directly when a space is
   named**, classified like any capture when not; `add_thought(id, text)`; `set_status(id,
   done|open)`, `set_due(id, date|null)`, `set_star(id, bool)`; `create_space(name)`. Offered text
   editing and deleting; the owner chose neither.
5. **Agents may create a space**, and the server's instructions tell every agent to list the
   spaces first and ask the owner before creating one. A skill only if clients ignore that.
   Note: there is no "learning with AI" space today (`ai-lab` exists); the owner may make one.
6. **Provenance recorded and shown**: the capture records source `mcp` and the client's name,
   and the item shows "via claude-code".

## Challenges raised

- **claude.ai web and desktop connectors need OAuth**; a header token is not enough. This slice
  serves header-token clients -- Claude Code, Codex, most CLI and IDE agents -- which is what the
  project workflow uses. An OAuth connector is a later slice if wanted.
- **Cloudflare can buffer streamed responses**, so the endpoint is stateless with plain JSON
  replies: one request, one answer.
- **Agents write unattended**, so provenance is visible and there is no editing or deleting; a
  wrong add is one tap to fix or delete by hand.
- **A new dependency**, the official `mcp` Python SDK, in the one module that speaks the
  protocol, rather than hand-rolling it.

## Build

- `mcp` in `backend/pyproject.toml`; `tartib/mcp_server.py` mounted at `/mcp` by `main.py`,
  stateless, JSON responses, the token checked in constant time.
- Tools reuse the store's own write paths -- `insert_item`, `update_fields`, the thoughts insert,
  `spaces.add_space`, and the capture path plus runner for classified adds -- so titles, links,
  the touch trigger and every rule behave exactly as in the app.
- Migration 0023: `captures.source` accepts `mcp`, and `captures.client` holds the client's
  name (from the MCP initialize handshake).
- The item page shows "via <client>" for an item whose capture came from MCP.
- Server instructions: list spaces first; ask before creating a space; prefer adding a thought
  to an existing item over a new near-duplicate.

## Out of scope

OAuth and claude.ai connectors; editing text; delete; Ask; sessions; a skill.

## Acceptance

1. No token or a wrong one: 401. `TARTIB_MCP_TOKEN` unset: `/mcp` does not answer.
2. `tools/list` shows the eleven tools, and no edit or delete tool exists.
3. The namazee flow: `list_items(namazee)` returns its open tasks first; `set_status` marks one
   done; `add_thought` records what happened.
4. `add_note(space="social-media")` files directly, source `mcp`, and the item page shows
   "via <client>".
5. `add_task` with no space goes through the classifier like a capture.
6. `create_space` creates one; adding to a space that does not exist fails with the list of
   those that do.

## Verification

- `pytest` with `test_mcp.py`, driving a real MCP client session against the app.
- One real client: Claude Code connected to the local `/mcp`, running the namazee flow once on
  development data.
- A security review of the endpoint before it ships: it is a second credential into the data.

## On ship

`technical.md`: the endpoint, the token, the tools. SPEC: "via <client>". `private.md`: the token
and how to connect a client. history.md.
