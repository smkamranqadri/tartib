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
  space and sized by how often an item is referenced. **Blocked on links**, below. This entry
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

Reported by the owner on 2026-09-22, the first day on v2.0, for the next cycle:

- **The title is confusing, and it cannot be edited where it is shown.** The owner's words: *"don't
  know title where note or task render, it duplicate and i can't edit it."* What the code does:
  a task's title is drawn as a heading **above** the text only when it differs from the whole
  body (`ItemPage.tsx`, the `item-title` line), so it appears in up to three places -- that
  heading, the list row, and the Title field in the Edit section -- and **only the last is
  editable**. Tapping the heading does nothing; tap-to-edit covers the body, not the title. A
  note has no title at all: its row shows its first line. And the capture box promises *"The
  first line becomes the title"*, which is only true of a task. Worth settling what a title *is*
  before changing where it shows: one editable thing in one place, shown the same way for a task
  and a note. Screenshot on file: a task "Post on social media" whose title sits over a checklist.
- **A checklist typed naturally does not become a checklist.** The owner typed `[x] post on
  linkedin` and `[] post on facebook`. The renderer *does* support task lists -- it draws a box
  from marked's `task` and `checked` fields -- but marked only recognises the GFM form, `- [x]` and
  `- [ ]`: without the leading `- `, and with `[]` instead of `[ ]`, those lines are a plain
  paragraph and render as literal brackets. Checked by feeding both forms to marked's lexer. Two
  things to decide: whether to accept the looser form people actually type, and whether the boxes
  should be **tickable** -- today they are drawn `readOnly disabled`, so even a correct checklist
  cannot be ticked, which is half a feature for a to-do list.
- **Deleting a note or task should ask in a modal, not inside the note's body.** The owner's
  words: *"should ask to delete note or task in modal not in note's body."* What the code does:
  Delete in the item page's header sets `confirmDelete`, and `Confirm` renders inline **below the
  text editor** (`ItemPage.tsx`), far from the button that asked. `Confirm.tsx` is inline by
  design ("with no dialog"), and so far the product has had no modal anywhere: the session outcome,
  the update bar and the stale-save strip all say so in their comments, and `technical.md` records
  "there is no modal, here or anywhere." This request reverses that for delete. Decide whether
  deleting a space (`Space.tsx`, the same `Confirm`) follows it, and whether the other inline
  questions stay as they are.

- **Links between items: approved, the owner's words "we definitely need links."** Raised while
  moving existing notes into Tartib (copied by hand -- no import feature is wanted). Two kinds,
  both from real notes:
  (a) note to note -- a CapRover setup note includes the Docker setup note, which includes the
  server setup note; one note should open the next, and the one linked to should show what links
  to it;
  (b) item to another space -- a task to build a console app belongs to its own work but also
  to `coding`. Today an item has exactly one space, so this is either a link to a space or an
  item living in more than one, and that is the larger decision.
  Undecided: how a link is written (`[[Title]]` is the familiar form, and notes have no title
  field -- the title entry above bears on it), what happens to a link when its target is renamed
  or deleted, and whether the classifier may propose links. Unblocks the item graph.
- **A space becomes one long flat list -- being tried with more spaces first.** Same report: the
  notes come from folders (`Documents`, `Feedback` with one note per person, and a `Resource`
  folder of about 27 notes mixing infra, reading, work and personal). Spaces are flat and a
  space is one list; the in-space tree was tried and dropped in slice 21. On 2026-09-22 the owner
  chose to split into narrower spaces, which needs no code, and see how it holds before designing
  anything. Revisit after links: an index note linking to its children may be structure enough,
  and sections or tags inside a space are the option if it is not.

- **Routines: recurring tasks. Asked for 2026-09-22 and not yet planned.** The owner's
  Routine note, copied from their old notes, has a daily group (check WhatsApp, Slack, email,
  stocks, server status, ten error-log entries) and monthly groups on rules like "1st Monday of
  Month" (rotating credentials across named servers), "1st Tuesday" (reviewing WordPress
  plugins) and "1st Wednesday" (disk cleanup). Tartib has no recurrence at all: no column, and
  nothing in SPEC; the only mention is that habits "stay undated" (checked 2026-09-22). The
  smallest shape that fits: a task carries a repeat rule (daily, weekly, the nth weekday of the
  month), and ticking it done moves `due` to the next occurrence instead of closing it, so it
  reaches Today on its day and reminders work unchanged. Two things it depends on: each group is
  a checklist, so **tickable checklists** (entry above) come first or with it, and ticking the
  routine done must reset its boxes. Undecided: whether a missed day piles up or skips, and
  whether the classifier may propose a repeat rule from text like "every 1st Monday".
  The owner will bring more detail when this is planned; what is here is only what the one note
  shows.
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

Unscheduled candidates:

- Image was 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). Slice 18 dropped the Claude CLI (1.07GB built locally on arm64, 2026-09-19; not measured on the x86_64 deploy build). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
