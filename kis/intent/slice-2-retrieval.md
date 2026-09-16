# Slice 2: retrieval (2026-09-17)

Read-only. No new item fields, no new shapes. Rule 4 relaxed to allow one read-only ask feature over existing items (user decision, 2026-09-17).

## Scope

1. All screen: search (FTS5 over raw_text + title), filters space, shape, status (open|done). Notes show raw text, tasks as on Today. Empty search = newest first.
2. Item page `/items/{id}`: full raw_text, proposal, created_at, inline edit of space/shape/due/star/status. Notes stay raw.
3. `POST /api/ask {question, space?}` -> `{answer, item_ids}`. FTS5 on question terms (OR, prefix), fallback to the 20 most recent in that space. Same Codex transport as classify, prompt answers only from those items and cites ids. Never writes.
4. Ask box on All: question in, answer out, cited items link to `/items/{id}`.
5. Visual direction from user screenshots: centered pill nav with icons, card sections with uppercase labels, subtle borders, theme toggle.

## Acceptance

Capture 10 notes across spaces. Find each by search. Ask "what did I decide about X?" and get a correct answer citing the right note, rendered as a link.

## Status

- [x] backend: codex transport shared, status filter, ask endpoint, tests
- [x] frontend: All filters + ask box, item page, restyle
- [x] proof: pytest, build, headless UI, real-Codex acceptance run (see kis/state/current.md)
