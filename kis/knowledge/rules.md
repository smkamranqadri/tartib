# Rules

Hard constraints. Do not relax without an explicit decision recorded here.

1. The AI never rewrites text. A capture's `raw_text` is immutable (what was typed, kept for comparison). A filed item's text belongs to the user and is editable (since 2026-09-17).
2. Capture never waits on AI. A capture request returns as soon as the row is stored.
3. (An approved replacement is planned in `../intent/slice-18-small-fixes.md`, step 1: the Claude fallback is removed and Codex is the only classifier. The rule below is what the code does today.) One set of prompts and schemas, run through CLIs as subprocesses. Primary: Codex CLI. Optional fallback when Codex fails: Claude Code CLI, same prompts (added 2026-09-17 after a Codex usage-limit outage). No HTTP provider.
4. (An approved narrowing waits in `../intent/backlog.md`: a space may list its own sessions, which is history without being a history screen. Charts, streaks, cycles and long-break logic stay banned. The rule below is what the code does today.) No projects, no tags. One read-only "ask" over existing items is allowed since 2026-09-17; it never writes.
   Push is allowed since 2026-09-17, for three things only: a reminder the user set on a task, one daily
   digest at a time you configure, and, since 2026-09-18, a session the user started, when it ends. Nothing
   else pushes, ever, and the third one stays silent when the app is already on screen. Pomodoro is allowed
   since 2026-09-17 as session logging only: no charts, no streaks, no history screen, no cycle or long-break
   logic. The rule these carve-outs preserve is that Tartib does not nag; it reminds you of what you asked it
   to remind you of. Each one was argued for on those terms, and the count is now three: a fourth needs a
   better reason than the third had.
5. One password from env. No user accounts, no signup.
6. Memory budget is 512MB for the whole compose stack.
7. (An approved narrowing waits in `../intent/backlog.md`: the classifier may *propose* a new space, which does nothing until accepted. The rule below is what the code does today.) Spaces live in the `spaces` table, managed from the Spaces page; `TARTIB_SPACES` only seeds an empty table. The classifier never invents one; an unknown space becomes null. A space can be deleted only when empty. There is no `inbox` space. A filed item always has a space.
8. (An approved replacement waits in `../intent/backlog.md`: disagreeing takes a reason and re-runs the classifier instead of rejecting. The rule below is what the code does today.) Reject discards the proposal and keeps the item in Needs Attention. Nothing is deleted by a decision. Explicit delete removes the item only; the capture stays.
9. Copy is calm and corrective, never guilt: something slipping asks for attention, it does not scold. Added 2026-09-19. It governs every string about overdue, stale or neglected things -- today `3d overdue`, `Stale tasks · untouched 14 days`, `All caught up`, and the digest -- and it governs what the model writes as much as what the code does, because the space brief and any future AI-written text are where scolding would creep in unnoticed: a prompt that produces user-facing prose says so. It is rule 4's reason applied to wording. Tartib does not nag in what it sends, and it does not nag in how it speaks.
