# Backlog

Approved work waiting for a plan, then defects, then candidates that are not required and may
never happen. How Tartib is built lives in `../knowledge/technical.md`; what each shipped slice
changed lives in `history.md`.

Slices 18 to 29 (2026-09-19 to -22) took most of what used to be here, and each left its proof in
its plan file. **When an entry ships, it leaves this file** -- it does not stay struck through.
That rule has been broken twice: eight entries slice 20 shipped sat here two days before anyone
noticed, and on 2026-09-22 five more were found struck through, one still claiming its slice was
"not yet closed" after it had. What is below is what is actually left, and nothing in it is
ordered yet.

Approved, not yet planned. Each gets a plan file when it comes up:

- **Ask becoming continuous.** Carried out of backlog entry 14 when it shipped as slice 27,
  because it is the one part that did not: Ask carries exactly one turn today (slice 26) -- the
  client sends the previous question and the items that answered it, and the server keeps no
  conversation. A real thread would need somewhere to keep it and a decision about how far back
  "that one" can reach. The other half of 14 that did not ship, multiple-choice answers, is not
  carried: a field holds one value and there is nothing like tags for a multi-answer to land in.
- **An item graph.** Notes and tasks as nodes, the links between them as edges, clustered by
  space and sized by how often an item is referenced. **Unblocked since slice 33** (links, `slice-33-links.md`), which gives the edges. This entry
  used to say slice 28 had shipped linking; it had not. Slice 28 added `duplicate_of`, one
  classifier-set pointer used only for the "Looks like #N" warning, and nothing a person can
  write (checked against the migrations, 2026-09-22). With no links there are no edges and the
  graph is a scatter of unconnected dots. A deterministic force layout drawn as plain SVG is
  enough, so this needs no charting or graph dependency.
- **Photo and voice on the capture box.** The mic already dictates into the text field with the
  browser's speech recognition, so speech-to-text is not the ask; keeping the audio itself is, and
  it raises the same question a photo does. Neither has anywhere to go today: captures are text,
  and the classifier is a subprocess fed a text prompt. Two routes, and 2026-09-19 decided to
  record both rather than choose blind:
  (a) attach only -- the file is stored and shown on the item, and whatever you type alongside is
  what gets classified; needs file storage beside the database, a size budget, and a decision
  about what backup means once the database is no longer the only state;
  (b) read it into text -- the image or audio goes through something that returns text, and that
  text is classified as usual; needs a vision or transcription route, and whether either CLI can
  accept a file on the deployed host is unestablished. Settle (b) first: if it is impossible
  there, (a) is the whole feature.
- **Backups for the deployed database.** Slice 17 step 4 called for a cron copying
  `/data/tartib.db` off the persistent directory and one restore actually performed; deferred
  2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so it is
  not a backup, and everything in that database exists exactly once.
- **A Needs attention count on the nav's Inbox. Asked for by the owner 2026-09-23.** The Inbox
  label in the nav should show how many items wait in Needs attention. Today there is a count
  only on the Inbox page's own tabs (SPEC, Inbox), and none in the nav. The nav is the header
  pills on a wide screen (`App.tsx`) and the bottom tab bar on a phone (`TabBar.tsx`). Both
  should show it, unless the plan decides otherwise. The count has to update when a card is
  decided (the `version` bump the Inbox routes already use), and like every count it may lag
  offline (SPEC, Offline). A zero should show nothing.

Reported by the owner on 2026-09-22, the first day on v2.0, for the next cycle:

- **A space becomes one long flat list -- being tried with more spaces first.** Same report: the
  notes come from folders (`Documents`, `Feedback` with one note per person, and a `Resource`
  folder of about 27 notes mixing infra, reading, work and personal). Spaces are flat and a
  space is one list; the in-space tree was tried and dropped in slice 21. On 2026-09-22 the owner
  chose to split into narrower spaces, which needs no code, and see how it holds before designing
  anything. **Links shipped with slice 33 (not yet deployed), so this is due for a look once they
  are in use:** an index note linking to its children may be structure enough, and sections or
  tags inside a space are the option if it is not.

- **Routines: recurring tasks. Asked for 2026-09-22 and not yet planned.** The owner's
  Routine note, copied from their old notes, has a daily group (check WhatsApp, Slack, email,
  stocks, server status, ten error-log entries) and monthly groups on rules like "1st Monday of
  Month" (rotating credentials across named servers), "1st Tuesday" (reviewing WordPress
  plugins) and "1st Wednesday" (disk cleanup). Tartib has no recurrence at all: no column, and
  nothing in SPEC; the only mention is that habits "stay undated" (checked 2026-09-22). The
  smallest shape that fits: a task carries a repeat rule (daily, weekly, the nth weekday of the
  month), and ticking it done moves `due` to the next occurrence instead of closing it, so it
  reaches Today on its day and reminders work unchanged. Each group is a checklist, and boxes
  are tickable since 2026-09-22 (`b420ed3`, `toggleTask` in `markdown.ts`); what is still missing
  is that ticking the routine done must reset its boxes. Undecided: whether a missed day piles up or skips, and
  whether the classifier may propose a repeat rule from text like "every 1st Monday".
  The owner will bring more detail when this is planned; what is here is only what the one note
  shows.
- **Notes in Pick for me.** Slice 32 picks from open tasks only; on 2026-09-22 the owner left
  notes out, to be thought through separately. Stars are task-only today (SPEC, task fields), so
  including notes means deciding what a picked note is and when it leaves Today.
- **A simple vault inside Tartib: the owner's direction, 2026-09-22, not now.** Credentials are
  the last of the owner's old notes with nowhere to go. A vault like Bitwarden was the question;
  the owner chose to build a simple one into the app, **kept in a separate database or separate
  tables**, later. Until it exists, no secret goes into an item. What any design has to answer,
  because of how items work today:
  - **It must never reach a prompt.** An item's text goes into model prompts beyond
    classification: Ask and the space brief read items and their thoughts (SPEC, Item page), and
    similar-item retrieval feeds the classifier. Vault entries must be outside every one of those
    paths, and outside search and FTS, by construction rather than by a filter.
  - **Encryption at rest.** The database is plain SQLite and one env password guards the app
    (rule 5); whether the vault needs its own key or unlock step is the central decision.
  - **Backup.** There is none for the deployed database (deferred 2026-09-18), and a lost vault
    is worse than lost notes.
  Items keep only pointers, such as "CapRover admin password: in the vault". The Routine note
  already does this: it names what to rotate and on which servers, never the secret itself.

Defects:

- **The desktop top bar should stay fixed, with its glass. Reported by the owner 2026-09-23 on
  `v2.3`.** It scrolls away with the page and has no fill. This is by design, not a regression:
  slice 18 made it sticky glass (`da7094f`, `9999ef4`), and slice 23 (`04b9be6`, 2026-09-20)
  deliberately took both away, because content scrolled under a translucent band and the capture
  box, update strip and first card were hidden behind it (`.top` in `frontend/src/styles.css`).
  The owner wants the sticky glass bar back, so the fix has to answer that old cost: content
  must not sit hidden under the bar when the page loads or when you jump to an anchor. That means
  a scroll offset and a fill solid enough to read through. It is desktop only, because on a phone
  the nav is the bottom tab bar (slice 22). The `html { overflow-x: clip }` that kept it sticky
  is still there.
- **Remove the row's hover pencil. Reported by the owner 2026-09-23.** The owner had already
  said it was not needed, but that was never recorded here. The ✎ that hover or long-press
  reveals on every row (`ItemRow.tsx`, the `Edit` link in `actions`) goes to the same `href` as
  the row's title, so it duplicates a tap on the title. It survives from slice 24, which kept
  "the pencil exactly as it is" (`slice-24-presentation.md`) when the title stayed a link.
  Since then the title does the same job, and since 2026-09-20 tapping the text is how you edit.
  Remove the pencil, keep Start session in the hover actions, and update SPEC's "hover or
  long-press reveals edit" (Rows).
- **A capture that needs attention is hard to act on from Home. Reported by the owner
  2026-09-23.** It has three parts, checked against the code 2026-09-24:
  - **Home's Recent shows waiting captures.** `queries.py:79` takes the last three captures
    whatever their stage, so a waiting item appears under both Recent and Needs attention.
    Inbox's own Recent tab already leaves out what waits (SPEC, Inbox). Home's Recent should do
    the same and show only what is filed.
  - **A Needs attention row on Home opens the item page**, because it uses the shared `ItemRow`
    link. The item page shows the proposal only as read-only fields plus the "File it" form
    (`ItemPage.tsx`). It has no Approve, Later or "Tell it why", no question buttons and no
    link chips, so the decision cannot be made there the way the Inbox card makes it. A waiting
    row should open the Inbox, at that item's card.
  - **Nothing outside Home says something is waiting.** The Inbox count in the nav (the entry
    above, Tartib #228) is the rest of the answer.

- **Forgetting to run a session. Reported by the owner 2026-09-24.** Work goes untracked because
  no session was started, or because the next one was not started after the last one ended.
  A design already proved in an earlier build of the owner's (substance only):
  - **Two states need a nudge.** *Overrunning*: a session is still running past its end and the
    person is active. *Untracked*: no session is running, the person is active, and the last
    session ended more than a grace period ago (5 minutes there). Being away (no input for 60s)
    or having just ended a session means no nudge. It was a pure function of four inputs, so it
    was unit-tested on its own.
  - **The nudges are scheduled with the system when a session starts**, at its end plus 5 and
    plus 15 minutes, and cancelled by the next start or stop. They are not posted when the app
    notices, because the app's own timers were exactly what stalled while hours went untracked.
    Rescheduling replaces what is pending, so a finished session's nudge never fires during the
    next one.
  - **An in-app pill says "Nothing is tracking"**, with Start on it and the off switch on the
    pill itself, not buried in settings.
  - What carries over to Tartib: its push is server-sent (reminders, slice 11), so the
    end-plus-5 and end-plus-15 nudges can be pushes the server schedules from `ends_at` and
    drops when another session starts. A browser cannot see idle time outside the page, so
    *untracked* can only be judged while Tartib is open and in focus (Page Visibility plus
    recent input), and the pill belongs beside the session card. Undecided: working hours,
    whether the untracked push exists at all or only the overrun one, and the off switch
    (Settings, Device, next to session sound). Rule 9 (Tartib does not nag) governs its wording:
    "Nothing is tracking" states a fact, and a scolding version does not.
- **Sessions on the item page. Asked for by the owner 2026-09-24.** The item page, which is also
  the panel beside a space's list (`Panes.tsx` renders `ItemPage`), shows only a Start session
  button. It says nothing about how many sessions the task has had or what they were. Wanted:
  the count, and the sessions themselves (when, how long, the outcome). The data exists, since
  `sessions.item_id` points at the item and `/api/sessions/recent` already lists finished
  sessions, but there is no filter by item.
- **A `set_reminder` MCP tool. Asked for by the owner 2026-09-24.** The MCP server (slice 35) can
  set `due`, `starred` and `status`, but not `remind_at`, so an agent that stars a task for today
  cannot also make it notify. That came up on the first real use, starring #240 over MCP. It is
  small: one tool beside `set_due`, going through the same update path the app uses so the
  reminder worker sees it.
- **Ask that can act. Asked about by the owner 2026-09-24.** For example "star #240 and remind me
  at 6" typed into Ask. Today Ask only reads, and **rule 4 says Ask never writes**, so this needs
  the owner to amend rule 4 before any plan. The two writing AI features so far (Pick for me, and
  the links that `suggest_links` proposes) were each allowed narrowly by name. The shape that fits
  that precedent: Ask proposes the change as a card, and nothing is written until the owner
  confirms it.
- **Start a session without a task, then attach it. Asked for by the owner 2026-09-24.** Starting
  without a task already works: `item_id` is nullable (`sessions.py`), and it is the session
  card's "Start for a fresh one". What is missing is attaching one afterwards. There is no
  endpoint for it: `/api/sessions` has start, stop, outcome, current and recent only. Wanted:
  while the session runs or at its outcome, pick an existing task (the `[[` picker's search
  fits) or create a new one from a line of text, and the session joins it. Its count then lands
  on that task in Today, and "done" as the outcome closes it (`sessions.py:124`). Undecided:
  whether an unattached session asks at its outcome, and whether a new task goes through the
  classifier or files into a space you choose.
- **Goals (or containers) inside a space: the owner's direction on 2026-09-23, not now.** The owner
  will use what is built first (links, Pick for me, link cards) and decide after that, so as not
  to build something that goes unused. The shape as it was described:
  - A goal belongs to one space and has its own due date, its own tasks and its own notes. An
    item is in one goal or in none, set by one field, not by a link. A filter needs an
    unambiguous yes or no, and links stay as they are.
  - The space page puts a row of goal cards above the list, styled like the space cards on
    Spaces, each with open and note counts, how many are done, and an overdue dot. Selecting a
    card filters the list below, and the All · Tasks · Notes · Done chips still apply. **The
    default view shows only items with no goal**: goal items are hidden from it on purpose, so
    the cards' counts are what stop them being forgotten.
  - "+ Add" with a goal selected files into that goal. Closing a goal takes its card out of the
    row, and its items stay in it.
  - The classifier sets a goal only when the capture says so ("new goal …", "this belongs to
    goal …"), the way it takes a named space. It never guesses one.
  - Undecided: the name (goal or container); whether Today, Inbox and search show an item's goal;
    and where closed goals are listed. Slice 21's tree inside a space was dropped on 2026-09-20.
    This is a filter rather than a tree, and the plan has to say why it will not end the same
    way.

Unscheduled candidates:

- **Clear the service worker's API cache on sign-out.** `tartib-api-v1` keeps every successful
  `/api/*` GET for offline reading and nothing empties it when you sign out, so whoever holds the
  device can read it offline. Older than v2.2; raised by its security review (2026-09-23).

- Image was 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). Slice 18 dropped the Claude CLI (1.07GB built locally on arm64, 2026-09-19; not measured on the x86_64 deploy build). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
