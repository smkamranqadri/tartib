# Tartib ARCHITECTURE

The architecture decided on 2026-09-17 is built and lives in `kis/knowledge/technical.md`. This file keeps only what is still intent.

## Open follow-ups

None required for v0.1. Candidates, unscheduled:

- Image is 524MB. Dropping `uvicorn[standard]` extras and bytecode compilation would shrink it; not a stated constraint (memory is, and runtime is 37MiB).
- Automatic retry for `proposal_error` items when the AI endpoint comes back. Today they wait for a human.
