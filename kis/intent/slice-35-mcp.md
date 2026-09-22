# Slice 35: Tartib over MCP

Planned 2026-09-23 with the owner. Standard mode.
**Built and verified 2026-09-23 (Proof, below); deployed as `v2.2` the same day, `/mcp` on.**

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

## Proof (2026-09-23, local)

- As built, differing from Build above: `captures.source` keeps `api` and a new
  `captures.client` names the agent -- `source` has a CHECK constraint SQLite can only change by
  rebuilding the table every item points at. The name comes from `?client=` on the URL, then the
  handshake, then the User-Agent; the `mcp` SDK is 2.2.0, where `FastMCP` is `MCPServer`. After
  review: a token under 32 characters leaves `/mcp` off, text is capped at 20,000, GET answers 405.
- `uv run pytest -q`: **362 passed, 9 deselected** (eleven in `test_mcp.py`, the SDK's own client
  over HTTP against the app under uvicorn: acceptance 1 to 6 -- the token the only way in, the
  login password refused, off unset or short; the eleven tools and no edit or delete; the namazee
  flow; a named-space note filed directly with "via" from the URL, the User-Agent, or neither; a
  spaceless task classified; an unknown space listing the real ones, a new space, tasks-only
  fields, bad dates, oversized text); schema asserts to 23; `ruff` clean.
- `npm run ui`: **20/20** on the rebuilt image, which carries `mcp` 2.2.0. `tsc` clean. Looked at
  on 390px and 1280px: "via claude-code" beside the space and age.
- **A real client**: Claude Code 2.1.280, headless (`claude -p`, a throwaway `--mcp-config`, nothing
  saved), against a throwaway Tartib on port 8002 with its own token and database. It listed
  namazee's open tasks, marked the Asr task done with the thought asked for, filed the
  social-media note directly, and, asked about a missing learning space, proposed `ai-learning`
  and did not create it, as the instructions say. The note showed "via claude-code" from its
  User-Agent alone. Run again after the hardening: nine POSTs, all 200, no GET. Everything was
  deleted after.
- **Security review** (a separate agent): no confirmed vulnerability. Every method and path
  variant without the token is 401 or falls to the SPA; only the one SDK route is mounted; SQL is
  bound; the `client` label is sanitised and rendered as text. Its three hardenings were taken
  (above). Noted: prompt injection through agent text into the classifier is inherent; `via` is
  self-asserted.
