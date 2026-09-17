# Backlog

Nothing here is required. How Tartib is built lives in `../knowledge/technical.md`.

Unscheduled candidates:

- Image is 1.46GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras). Not a stated constraint (memory is, and runtime is 42MiB). A slimmer route: download the Codex release binary instead of npm.
- Automatic retry for `proposal_error` items after a Codex outage or usage-limit block. Today they wait for a human. Seen for real on 2026-09-17 when the ChatGPT usage limit hit mid-deploy.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. If recall becomes a problem, the cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings.
