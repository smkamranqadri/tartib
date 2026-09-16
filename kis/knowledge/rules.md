# Rules

Hard constraints. Do not relax without an explicit decision recorded here.

1. A capture's `raw_text` is immutable, and so is each item's excerpt. Classification proposes fields around the text and never rewrites it.
2. Capture never waits on AI. A capture request returns as soon as the row is stored.
3. One classifier only: the Codex CLI run as a subprocess. No HTTP provider, no second adapter. (Changed 2026-09-17 from an OpenAI-compatible endpoint; the user has no API endpoint.)
4. No projects, no tags, no pomodoro, no push notifications. One read-only "ask" over existing items is allowed since 2026-09-17; it never writes.
5. One password from env. No user accounts, no signup.
6. Memory budget is 512MB for the whole compose stack.
7. Spaces exist only in `TARTIB_SPACES`. The classifier never invents one; an unknown space becomes null. There is no `inbox` space (removed 2026-09-17). A filed item always has a space.
8. Reject discards the proposal and keeps the item in Needs Attention. Nothing is deleted by a decision.
