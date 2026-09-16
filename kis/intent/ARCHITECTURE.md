# Tartib ARCHITECTURE

The architecture decided on 2026-09-17 is built and lives in `kis/knowledge/technical.md`. This file keeps only what is still intent.

## Open follow-ups

None required for v0.1. Candidates, unscheduled:

- Image is 1.13GB (Node runtime + Codex CLI + uvicorn extras). Not a stated constraint (memory is, and runtime is 42MiB). A slimmer route: download the Codex release binary instead of npm.
- Automatic retry for `proposal_error` items after a Codex outage. Today they wait for a human.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
