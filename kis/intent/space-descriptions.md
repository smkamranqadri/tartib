# Space descriptions

Owner-approved scope, 2026-10-07. Standard mode on `cycle-space-descriptions`.
The owner approved the design and said “looks good, let’s proceed” on 2026-10-07;
implementation is authorized and in progress on this branch.
Shared State belongs to the coordinator and is not changed by this stream.

## Cycle decisions

Approved cycle: #378 space descriptions first, then #243 Home Needs attention,
#228 navigation Inbox count, and #281 session finish sound. Backups are a separate
operational track. This branch owns #378 only.

- #378: owner-written descriptions explain a space's purpose to agents without
  inferring it from names or items. No invented or seeded live descriptions.
- Q1: both app UI and MCP, with REST support for the app.
- Q2: maximum 500 characters; empty clears. Normalize and count consistently across
  UI, REST and MCP; invalid input writes nothing.
- Q3: `set_space_description`; keep names-only `list_spaces.spaces` and add details.
- Q4: YES. Descriptions guide automatic classification. The earlier recommendation
  to defer classification is superseded by the owner's explicit decision.
- Saves require a token advancing on every accepted write, including clear or
  same-text saves. Millisecond precision alone is insufficient; CAS and a guaranteed
  advancing value must be proved for same-clock and concurrent callers.
- Coordinator monitors foreground work and permission prompts. Work alone; no
  commits, deploys, production writes or seeded owner descriptions.

## Planned scope and acceptance

Add description and stale-token storage through an additive migration. Preserve
space rename/delete behavior, MCP name ordering and existing readers. Share domain
validation; REST uses HTTP errors and MCP uses ToolError. Prove migration and old
v2.6 startup/read/create/rename/delete on the new schema before claiming rollback.

Expose an app editor and descriptions on Space pages and Spaces cards. Preserve
Panes, filing-policy explanation and controls; generic subtitles are hidden on
phones, so descriptions need a dedicated visible region. Use the app modal,
500-character counter and spinner-only Save. Retain draft text on stale/error;
blank save clears. Owner approved the desktop and phone exports on 2026-10-07;
implementation is authorized from those references.

Propagate owner descriptions through classification and redo context as quoted
filing data. Preserve canonical allowed spaces, house rules, confidence thresholds
and auto/ask/file behavior; descriptions do not create spaces or rewrite items.
Brief and Ask behavior are outside this feature.

Proposed hard space-context bound: 12,000 characters including wrappers, split into
at most 8,000 description characters and 4,000 existing counts/examples. Keep the
canonical allowed-name list in its separate prompt section. Allocate description
excerpts fairly and deterministically when full texts do not fit, mark truncation,
and never alter stored text or generate summaries. Drop optional examples/count
detail to enforce the hard bound. This does not claim the entire prompt is capped.
Check exclusion-heavy descriptions because truncation can remove guidance.

Compare baseline and described-space classification on identical captures, model,
reasoning, time and prior examples. Key evidence by fixtures and renderer version,
including descriptions. Freeze expected outcomes before running; include clear,
ambiguous, overlapping/exclusion, cleared, long/truncated and adversarial cases.
Report correct filing, wrong-space filing, attention rate and context size by arm.
Repeat matched comparisons if results vary. Existing unambiguous cases and filing
safeguards must hold; targeted purpose cases must use the descriptions.

Run relevant storage/API/MCP/classifier/runner checks, then the non-eval suite and
matched real-model evals. Mutation-check new guards and description propagation,
restoring saved originals. Visually inspect rendered UI after changes.
## Status (2026-10-07, resume verification)

Implemented on this branch, uncommitted. Proved locally: non-eval backend suite 397
passed (10 evals deselected), ruff clean, typecheck and build, `npm run ui` 23/23, the
four rendered exports compared with the approved ones, and `set_space_description` over
`/mcp` on a scratch database (set, readback, stale refused, 501 refused, clear, unknown
space). Every guard was mutation-checked; the two equivalent survivors are in
`design-handoff.md`.

Not done: the live described-versus-baseline eval (it calls Codex, quota spent); the
rollback proof (v2.6 started on a schema-25 database); the `SW_VERSION` bump, which
belongs to the release; the Spaces-card preview was asserted by `npm run ui`, not
compared with a design export. Deploying needs a database copy first (migration 0025).

## Design and detailed review references

Concrete brief: `../../../../tartib.reports/space-descriptions/design-brief-space-descriptions.md`.
Detailed implementation plan and corrections are beside it in `plan.md` and
`report-codex.md`; owner decisions are in `questions.md`. These are run artifacts.
The brief uses current source layouts and real space names. Its proposed tartib
description is an explicit review draft, not existing data or permission to save.
