# Backlog

Two lists: work that is approved and waiting for a plan, then candidates that are not required
and may never happen. How Tartib is built lives in `../knowledge/technical.md`.

Approved on 2026-09-17, not yet planned. Only slice 11 has a plan file; these get one each
when they come up:

- **12 pomodoro** — sessions table, browser timer, top bar, end sheet with three outcomes,
  counts on Today and in the brief prompt. Depends on 11 for the session-done push, and the
  brief fingerprint will not notice session counts as it stands.
- **13 presentation** — markdown on the item page, note bodies and briefs; a live editor that
  styles as you type and never rewrites the stored bytes; eight themes in Settings; delete the
  redundant Edit link at `frontend/src/components/ItemRow.tsx:79`.
- **14 AI contract** — the classifier prompt editable and stored as an override with the
  default shipped in code; Ask becomes continuous.

Unscheduled candidates:

- Image is 1.46GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras). Not a stated constraint (memory is, and runtime is 42MiB). A slimmer route: download the Codex release binary instead of npm.
- Automatic retry for `proposal_error` items after a Codex outage or usage-limit block. Today they wait for a human. Seen for real on 2026-09-17 when the ChatGPT usage limit hit mid-deploy.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. The cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings. Slice 14 needs this, not just wants it: a follow-up like "what about the second one?" has no content words, so the OR-query returns nothing.
