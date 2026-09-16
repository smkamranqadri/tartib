# Slice 4: classifier fixes (approved 2026-09-17)

Absorbs slice 3 (Today recent, ask bar, space select). No new screens. No new item fields beyond `capture_id`.

## Decisions

- Captures are stored once (`captures` table, raw_text immutable). Items reference `capture_id`. One capture can produce many items.
- Proposal carries a verbatim `text` excerpt; `item.raw_text` = excerpt, fallback full capture text.
- Spaces come from `TARTIB_SPACES` (required, comma-separated). No `inbox` space. Filed items must have a space. Space outside the list is a 422.
- Classifier returns `{"proposals": [...]}`; shapes task | note | question. question -> no item; the runner runs ask on the text and stores the answer on the capture. space null or confidence < 0.85 -> attention; else filed. AI off or error -> one note item, space null, attention, proposal_error set.
- Reject discards the proposal (note, space null, dates cleared) and keeps the item in Needs Attention. Approve requires a space.
- Migration 0002 rebuilds `items`: backfills one capture per item, `space='inbox'` -> NULL and stage attention, old stage=inbox placeholder items dropped (their captures stay pending and are re-classified).
- 15-capture fixture runs against real Codex only under `pytest -m eval`. Default suite uses the fake CLI.
- `captures.source`: web (cookie), api (bearer), migrated.

## Phases

1. Backend: migration, config, capture pipeline, captures endpoint, prompts, store validation, tests.
2. Frontend: capture polling and answer panel, Today Recent card, sticky Ask bar, space select, Reject/Approve changes.
3. Eval fixtures, docs, live volume migration (copy first), acceptance run.

## Acceptance

- "Renew passport, call the dentist, and buy milk" -> three tasks with own excerpts, one capture id, visible in Recent.
- "what did Ali say about the API rate limits?" -> no item; answer with linked item in PWA and via `GET /api/captures/{id}`.
- Capture with no fitting space -> Needs Attention with empty space; Approve without a space refused; with one, filed.
- Live compose DB migrates in place; old inbox items in Needs Attention; row counts equal; search works.
- Recent on Today; sticky ask bar usable over a 30-item list at 390px; space select lists every configured space.
- `pytest -m eval`: 15 fixtures pass on shape and split count; spaces always within config.

## Status

- [x] Phase 1 backend
- [x] Phase 2 frontend
- [x] Phase 3 eval, docs, live migration (2026-09-17)
