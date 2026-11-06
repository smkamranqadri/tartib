# Changelog

Each release is a Docker image tag, `smkamranqadri/tartib:vX.Y`. The reasoning behind every
change is in [`kis/intent/`](kis/intent/), one file per slice.

## v2.9 (2026-11-06)

No migration and no frontend change; the service worker stays at `2026-10-15.1`, and rolling
back to v2.8 is clean.

- **MCP sessions:** `start_session`, `get_session` and `end_session` let an agent run the owner's
  focus timer. Replies carry `server_time` and `remaining_seconds`; an outcome can be recorded
  when ending (`done` ticks the task off, as `set_status` does). The end-of-session push is the
  app's own.
- **MCP `reminders_due(until, since?)`:** open tasks with a reminder up to a time, across all
  spaces, including ones already pushed, for a client that keeps its own record of what it acted
  on. Read-only.

## v2.8 (2026-11-05)

No migration and no frontend change; the service worker stays at `2026-10-15.1`.

- Python dependencies: `pyjwt` 2.15.1 and `multidict` 6.9.1, both for published advisories.
- README rewritten, with new screenshots taken from a seeded demo database, plus `SECURITY.md`,
  this changelog, CI, and issue and pull request templates.
- `.env.example` and the deploy guide document `TARTIB_MCP_TOKEN`, `TARTIB_AI_REASONING`,
  `TARTIB_DUPLICATE_PARK` and `TARTIB_LINK_PROPOSALS`.

## v2.7 (2026-10-15)

- **Space descriptions:** an owner-written description per space (up to 500 characters), shown
  on the space page and Spaces cards, editable in the app, over REST and through the MCP
  `set_space_description` tool, and used as context when filing (migration 0025).
- Home shows what needs attention; the nav shows the Inbox count; a session ends with a sound.
- MCP `search` and `list_items` return each item's first line and a snippet instead of its whole
  text.

## v2.6 (2026-10-07)

- MCP `find_replace`: literal replace-all in one item, scoped to its text, its thoughts or both,
  refused when an expected count does not match.

## v2.5 (2026-09-28)

- MCP `set_reminder` for tasks.

## v2.4 (2026-09-27)

- Editing and deleting: agents over MCP can edit an item's text (only with its current
  `updated_at`), delete items, and edit or delete thoughts.

## v2.3 (2026-09-23)

- Link cards say what they decide: Link N, No links or Later.

## v2.2 (2026-09-23)

- **MCP:** agents connect to `/mcp` with their own token to list, search, read and add items.
- **Links:** `[[Title]]` and `[[space:name]]`, plus `python -m tartib.suggest_links` to propose
  links for items already filed.
- **Pick for me:** the AI stars up to three open tasks to work on next.

## v2.1 (2026-09-22)

- A capture that splits waits for you instead of filing every piece.
- One title per item, one control shape, and questions asked in a modal.

## v2.0 (2026-09-22)

- The UI language, phone-first layout, space pages, offline reading of the shell, Markdown.
- The classifier sees what already lives in each space, takes your house rules, can name a
  duplicate, and records the cost of every call.
- Failed captures retry themselves, and each waiting item says why it waits.

## v1.0 (2026-09-18)

- Capture, classify and file into spaces, Needs Attention, Ask and space briefs, push reminders
  with a daily digest, pomodoro sessions, the installable PWA with an offline capture queue, and
  deployment behind HTTPS with a rate-limited password.
