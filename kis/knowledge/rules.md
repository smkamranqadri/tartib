# Rules

Hard constraints. Do not relax without an explicit decision recorded here.

1. The AI never rewrites text. A capture's `raw_text` is immutable (what was typed, kept for comparison), and a database trigger enforces it. A filed item's text belongs to the user and is editable (since 2026-09-17). **An item's text starts as whatever the classifier returned as its excerpt**: it is asked for a verbatim slice of the capture, but that is an instruction, not a check -- nothing verifies the excerpt is a substring. The capture's own text is the one that cannot drift, which is why it is kept.
2. Capture never waits on AI. A capture request returns as soon as the row is stored.
3. One set of prompts and schemas, run through the Codex CLI as a subprocess. No second CLI and no HTTP provider. A Claude Code CLI fallback existed from 2026-09-17 to 2026-09-19; it was removed because it never ran on the deployed host and made every Codex failure cost the full timeout. When Codex fails, the capture parks in Needs Attention with `proposal_error`.
4. No projects, no tags. One read-only "ask" over existing items is allowed since 2026-09-17; it never writes.
   Push is allowed since 2026-09-17, for three things only: a reminder the user set on a task, one daily
   digest at a time you configure, and, since 2026-09-18, a session the user started, when it ends. Nothing
   else pushes, ever, and the third one stays silent when the app is already on screen. Pomodoro is allowed
   since 2026-09-17 as session logging only: no charts, no streaks, no cycle or long-break logic, no totals
   over time. Since 2026-09-19 (slice 20) the session card shows the last few sessions and a space's page lists
   its own, newest first, one plain line each -- history made visible, never a history screen of its own. The rule these carve-outs preserve is that Tartib does not nag; it reminds you of what you asked it
   to remind you of. Each one was argued for on those terms, and the count is now three: a fourth needs a
   better reason than the third had.
5. One password from env. No user accounts, no signup.
6. Memory budget is 512MB for the whole compose stack.
7. Spaces live in the `spaces` table, managed from the Spaces page; `TARTIB_SPACES` only seeds an empty table. **The classifier never creates a space.** It may *propose* one that does not exist (since 2026-09-21), and a proposal does nothing: the item waits with no space, exactly as an unknown space leaves it, and only a person approving it creates the space. A name that already exists or fails the Spaces page's rules is dropped rather than offered. An unknown space the classifier names outright becomes null. A space can be deleted only when empty. There is no `inbox` space. A filed item always has a space. (Narrowed 2026-09-22 from "the classifier never invents one", which stopped being true when slice 28 shipped: the rule was always about a classifier free to spray one-off spaces across the database, and a proposal that needs a human to act on it cannot do that.)
8. There is no Reject (since 2026-09-19, slice 20). Disagreeing with a proposal takes a reason and asks the classifier again with it; the new proposal follows the normal filing rules and the space's policy, so a confident one files itself. Every reason is kept on the item (`feedback`, one dated line each) and the item's text is never touched by it (rule 1). Items rejected before then keep their empty proposal. Nothing is deleted by a decision. Explicit delete removes the item only; the capture stays.
9. Copy is calm and corrective, never guilt: something slipping asks for attention, it does not scold. Added 2026-09-19. It governs every string about overdue, stale or neglected things -- today `3d overdue`, `Stale tasks · untouched 14 days`, `All caught up`, and the digest -- and it governs what the model writes as much as what the code does, because the space brief and any future AI-written text are where scolding would creep in unnoticed: a prompt that produces user-facing prose says so. It is rule 4's reason applied to wording. Tartib does not nag in what it sends, and it does not nag in how it speaks.
