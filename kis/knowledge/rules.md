# Rules

Hard constraints. Do not relax without an explicit decision recorded here.

1. The AI never rewrites text. A capture's `raw_text` is immutable (what was typed, kept for comparison). A filed item's text belongs to the user and is editable (since 2026-09-17).
2. Capture never waits on AI. A capture request returns as soon as the row is stored.
3. One set of prompts and schemas, run through CLIs as subprocesses. Primary: Codex CLI. Optional fallback when Codex fails: Claude Code CLI, same prompts (added 2026-09-17 after a Codex usage-limit outage). No HTTP provider.
4. No projects, no tags. One read-only "ask" over existing items is allowed since 2026-09-17; it never writes.
   Push is allowed since 2026-09-17, for two things only: a reminder the user set on a task, and one daily
   digest at `TARTIB_SUMMARY_TIME`. Nothing else pushes, ever. Pomodoro is allowed since 2026-09-17 as session
   logging only: no charts, no streaks, no history screen, no cycle or long-break logic. The rule these two
   carve-outs preserve is that Tartib does not nag; it reminds you of what you asked it to remind you of.
5. One password from env. No user accounts, no signup.
6. Memory budget is 512MB for the whole compose stack.
7. Spaces live in the `spaces` table, managed from the Spaces page; `TARTIB_SPACES` only seeds an empty table. The classifier never invents one; an unknown space becomes null. A space can be deleted only when empty. There is no `inbox` space. A filed item always has a space.
8. Reject discards the proposal and keeps the item in Needs Attention. Nothing is deleted by a decision. Explicit delete removes the item only; the capture stays.
