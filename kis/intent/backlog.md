# Backlog

Approved work waiting for a plan, then defects, then candidates that are not required and may
never happen. How Tartib is built lives in `../knowledge/technical.md`.

Slices 18 to 22 (2026-09-19 and -20) took most of what used to be here -- the two defects, the
small items, the session card, the space page and the phone layout -- and each left its proof in
its plan file. What is below is what is left, and nothing in it is ordered yet.

Approved on 2026-09-17, not yet planned. Each gets a plan file when it comes up:

- **13 presentation** — **done as slice 24** (`slice-24-presentation.md`), both phases proved,
  not yet deployed. This entry closes when the slice is committed; what it established that
  outlives it is in `../knowledge/technical.md`. Two sub-items ended differently than written:
  the row title **keeps** its link (slices 21 and 22 made the row the tap target, which the
  2026-09-17 decision predates), and the pencil was already in `ItemRow`.
  Markdown on the item page, note bodies and briefs, rendered and edited
  in the same place: no edit mode to enter and no button to enter it, the text styles as you type,
  and the stored bytes are never rewritten.
  **The themes half is closed, not waiting.** It was attempted twice on 2026-09-20 -- six own
  palettes, then eight named ones, thirteen, ten, all scrapped; then seven generated ones, built,
  committed and removed the same day on the owner's call ("we have already spent too much time on
  it"). The app ships one theme, bronze. Do not re-open this without a reason that is not "more
  palettes"; what the two attempts actually established is below, and it survives in
  `frontend/tools/themes.py` and `themes.md`.
  The row keeps its pencil and the title stops being a link instead. This reverses the
  2026-09-17 decision to delete the pencil: it was redundant because the title went to the same
  place, but a title that is a link cannot be selected and copied, and copying the title is worth
  more than losing the duplicate control. The pencil is the `aria-label="Edit"` link in
  `frontend/src/components/ItemRow.tsx`, line 93 on 2026-09-19; line numbers drift.
  Decided 2026-09-20 while planning slice 23, so this does not get re-argued: the editor **is**
  CodeMirror, lazy-loaded (`@uiw/react-codemirror` with `@codemirror/lang-markdown`); `marked`
  parses the read-only places; and markdown reaches item text, the space brief, Ask answers and
  the thought log. The lighter overlay the entry used to ask for was costed and fails on a hard
  limit rather than a preference: a transparent textarea over a styled mirror can change a
  token's colour but not its size or weight, because the caret comes from the textarea's own
  uniform metrics -- so a heading drawn larger in the mirror puts the caret where the text is
  not. Colour-only highlighting and a focus-swap are the zero-dependency alternatives, and
  neither makes a heading look like a heading while you type it.

  **What the two theme attempts established**, beyond what `../knowledge/themes.md` now holds:
  - **The accent must not sit in the background's own hue family.** This decides whether a theme
    has character at all: a jade accent on a jade ground is 11 degrees apart and reads as one
    wash, green on indigo is 102 and reads as a theme. Dark teal with amber -- the pairing the
    owner already liked -- is the shape to aim for.
  - **Palettes drawn for terminals do not map cleanly.** A terminal theme defines one background
    and this app needs four, and every such palette's own comment colour fails AA on its own
    background, because a comment is *meant* to recede.

  The contrast floors, the surfaces they are measured against and the generator that enforces
  them are Knowledge now: `../knowledge/themes.md`.

- **14 AI contract** — the classifier prompt editable and stored as an override with the
  default shipped in code; Ask becomes continuous.
  Also: the classifier may ask *you* a question instead of only handing over a proposal it is
  unsure about. A structured block -- the question, single or multiple choice, and two to six
  options with short labels and an optional detail line -- so a low-confidence capture becomes
  "Which space?" with the candidates as buttons rather than a null field and an edit form. Decided
  2026-09-19; this changes the proposal schema, which is why it sits inside 14. Name it carefully:
  `shape: "question"` already means the user asked Tartib something, and this is the other
  direction.
  Also: your own corrections become the classifier's examples. Every item keeps the AI's original
  `proposal` after filing, so wherever you changed the space, shape, title or due date, the
  correction is already a diff in the database that nothing reads. Feed the recent ones in as
  few-shot examples, padded with high-confidence items you accepted untouched when there are too
  few. No schema change. Measured on an earlier build of the same idea: steering went 0/4 to 4/4,
  and over-application -- a correction applied where it did not belong -- went 1/2 to 0/6 only
  after a prompt fix, so test for that specifically. Decided 2026-09-19.

Slice 20 (`slice-20-round-three.md`, planned 2026-09-19) takes: add directly, filing policy
per space, skeleton rows (from "UI polish"), search that lands on the line, the session card,
the space page split view, tell it why, and the thought section. They leave when it closes.

Slices 18 and 19 (`slice-1{8,9}-*.md`) closed on 2026-09-19 and their entries have left this
file. Dropped the same day as already true: "a notification key that cannot fire twice" --
all three pushers hold a once-only guard (`reminded_at`, `digest_date`, `notified_at`).

Approved on 2026-09-19, not yet planned and none of it sized. "Link, don't duplicate" is scope for 14
rather than work beside it:

  Also, moved in 2026-09-19 from the approved list -- **one set of shared rules across both prompts.** Tartib has two prompts, classify and ask, and
  each carries its own copy of the item header format and the datetime handling. Two copies of
  one rule drift: on an earlier build the two prompts ended up disagreeing about the single rule
  they shared, one saying never invent a domain and the other saying null beats a wrong one,
  without anyone deciding it. Shared rules live once; each prompt adds only what genuinely
  differs. Do this before or with 14 -- an editable override is far more dangerous laid over two
  copies that have already diverged.

Defects, found on 2026-09-20 while attempting the themes and **still true of the shipped
teal pair**, independent of any theme work:

~~The session card's button fails AA~~, ~~the light theme's primary button is 3.5:1~~ and
~~`--muted` is not measured against the card header~~ -- **all three fixed in slice 23**
(`slice-23-ui.md`), which replaced both themes with one and measured every colour against the
surface it sits on: the session button is 5.21:1 and muted on a card header is 5.41:1.

Deferred from a slice rather than never planned:

- **Link, don't duplicate.** The classifier prompt should attach a capture to an item that
  already exists instead of filing a near-duplicate beside it. Needs retrieval at classify time,
  which the prompt does not have today: the classifier sees the spaces and the datetime, not the
  items. Belongs with 14, and changes what a proposal is -- it would have to name an item to
  update, which the schema has no field for.
  This is proven, not speculative. On an earlier build, giving the classifier real context from
  the database -- the structure of the spaces and the items that already exist, instead of a flat
  list of names -- took discriminating cases from 1/6 to 5/6. Duplicate detection that *parked* a
  suspected duplicate in review naming the item it matched, rather than filing it or merging it
  silently, caught 3/3 real duplicates with 0/5 false positives and no invented references. Park
  and name the match; do not auto-merge. Build the context server-side, so there is one source of
  truth for what the classifier is shown.
- **Add a task or a note directly.** Not everything is a thought to be classified; sometimes the
  shape and the space are already known. A form that writes a filed item without a capture and
  without an AI call. Note that a filed item today always has a `capture_id`, so this needs a
  decision about what that field holds when nothing was captured.
- **A thought section on notes and tasks.** A place on the item for your own thinking, kept
  separate from the item's text: an append-only log of dated entries rather than one field where
  the last edit wins, with the entry count shown on the item. Decided 2026-09-19 after seeing the
  same shape work elsewhere -- one document holding many entries behind a separator, counted in
  the list. Still open when planned: whether FTS5 indexes the entries, and whether Ask and the
  space brief may read them.
- **AI usage on record.** Count the calls and the tokens, per call and in total, and show them.
  The CLIs are subprocesses, so whatever they report on stdout is the only source; whether the
  Codex CLI reports token counts at all is unestablished and decides how much of this is
  possible. Both CLIs run on a subscription and will report no cost, so any money figure is an
  estimate: price the tokens from a model price catalogue fetched at most once a day and cached
  on disk, keeping the last good copy when a fetch fails (models.dev publishes one as JSON, USD
  per million tokens). Counts are the feature; the cost is a derived number and should read
  as one.
- **An item graph.** Notes and tasks as nodes, the links between them as edges, clustered by
  space and sized by how often an item is referenced. This is the whole point of linking, and it
  is blocked on "Link, don't duplicate" above: with no links there are no edges and the graph is
  a scatter of unconnected dots. A deterministic force layout drawn as plain SVG is enough, so
  this needs no charting or graph dependency.
- **Search that lands on the line.** An FTS5 hit carries the line or offset it matched, and the
  item page opens scrolled to it with the match marked, instead of opening at the top and leaving
  you to find it. Short notes hide the need for this; markdown bodies and thought logs end that.
- **Tell it why, instead of rejecting it.** Disagreeing with a proposal takes a sentence from you
  and re-runs the classifier on the same capture with your words as extra context. This
  **replaces Reject**: a disagreement always produces another attempt, never a parked item with
  the proposal thrown away. Decided 2026-09-19, and it rewrites rule 8, which today says Reject
  discards the proposal and keeps the item in Needs Attention -- rewrite the rule when this ships,
  not before. Keep the reason stored on the item: it is the only record of why the first answer
  was wrong, and the raw text still must never be rewritten (rule 1). Costs one AI call per
  disagreement.
- **The classifier may propose a space that does not exist yet.** A proposal only: naming it does
  nothing, and accepting it is what creates the space. An unaccepted proposal leaves the item
  where an unknown space leaves it today, at null with confidence capped. Decided 2026-09-19. Rule
  7 says the classifier never invents a space, and it says that because a classifier free to
  invent sprays one-off spaces across the database; this narrows the rule rather than dropping it,
  and the wording needs updating when it ships.
- **A filing policy per space.** A column on `spaces` that overrides the confidence rule in both
  directions: a space that never auto-files and always asks, and a space that always auto-files
  whatever the confidence. Today one global 0.85 threshold decides everything. A rule the database
  enforces, not an instruction in a prompt -- a prompt can be ignored, and elsewhere this exact
  gate exists because the prose version was ignored once.
- **Offline read, and offline edit.** — **done as slice 25** (`slice-25-offline.md`), proved,
  not yet deployed. This entry closes when the slice is committed; what outlives it is in
  `../knowledge/technical.md`. Two things it settled differently than written: editing text
  offline needs one idle moment online first (the editor is a lazy chunk the worker can only
  cache once it has been fetched), and counts lag by decision rather than by oversight.
  The original entry, for the record:
  The app goes blank of data the moment the network does.
  Proved in Chrome at 390px on 2026-09-19 against the local container: with the context offline,
  the shell and the nav render, Today says "You're offline.", Needs Attention and Recent are
  empty, and an item captured minutes earlier is not there. A cold start in a new tab behaves the
  same, so this is not a stale-tab effect. Capture is *fine* -- the queued capture appeared as
  "waiting to send - just now" with a "Saved offline" toast -- so this is about reading and
  editing only.
  Cause: `frontend/public/sw.js` returns early for every path starting with `/api/`, so no
  response the app reads is ever cached. Editing has a second cause: `frontend/src/offline.ts`
  holds one store, `pending-captures`, so an edit made offline has nowhere to wait.
  Slice 15 put this out of scope in as many words -- "offline read of Today or Inbox ... that is a
  separate argument on a separate day" (`slice-15-pwa.md`) -- so the behaviour is deliberate, not
  a regression. This entry is that separate day.
  Two things to settle when it is planned. Cached data is stale data, and Tartib's items change,
  so the screens need to say what they are showing and how old it is rather than quietly serving
  yesterday. And slice 15 argued conflict resolution was unnecessary because captures are
  append-only and `raw_text` is immutable -- true for captures, false for edits, which have been
  editable since 2026-09-17. A queue of offline edits lands exactly on the stale-save check
  slice 19 shipped (`expected_updated_at`, a 409 on a moved item): a replayed edit must carry the
  version it was made against, and a refused one needs somewhere to show Reload or Overwrite.
  Keep classification on the server when this is built. An earlier build let each device classify
  what it had queued, and one capture became a note on the laptop and a task on the phone at the
  same time. Tartib's runner is already the only classifier; an offline queue must replay raw
  captures and edits to it, never decide anything locally.
- **UI polish, phone first.** Two specifics, independent of each other (safe areas and the nav surface shipped in slice 18):
  *Skeleton rows* -- every card shows a bare `...` while it loads and then jumps when data lands;
  placeholder rows in the shape of the content hold the layout still.
  *Typography and controls* -- **done in slice 23**: JetBrains Mono bundled and self-hosted with
  no CDN, one button scale (a bordered pill, mono caps, one filled primary per screen), and every
  colour from tokens. What is left of this entry is skeleton rows.
  Note what is already done: slice 10 was the consistency pass -- one header convention, extracted
  `Row`, `Menu`, `Confirm`, `NameForm`, `Status`, one primary button class. This entry is the
  visual layer on top of that, not a second pass at the same problem, and planning it should start
  by reading what slice 10 settled.
- **The space page should not cost a round trip per item.** Today every row in a space is a link
  to `/items/{id}`, so reading one item is a full navigation and reading the next means going back
  first. Wide screens get the list on one side and the item on the other, so picking through a
  space is one click per item and the list never moves; phones keep the page they have, because a
  split does not fit 390px. The space page already collapses Tasks and Notes and remembers which
  was open -- that state has to survive the new layout, not be rebuilt by it.
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
- **A session card.** A countdown circle, the controls, and the last two or three sessions shown
  on the card once you stop -- replacing the slim bar, which shows a countdown and nothing else.
  Plus the sessions for a space listed on that space's page. That last part amends rule 4, which
  allows pomodoro as session logging with "no history screen": a space showing its own sessions is
  history, even though it is not a separate screen. Approved 2026-09-19 on those terms -- the ban
  on charts, streaks, cycles and long-break logic stands, and rule 4 gets the narrower wording
  when this ships. Sessions already reach the space indirectly, since the brief is given per-task
  session counts, so this is the same data made visible rather than new data.
- **Backups for the deployed database.** Slice 17 step 4 called for a cron copying
  `/data/tartib.db` off the persistent directory and one restore actually performed; deferred
  2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so it is
  not a backup, and everything in that database exists exactly once.

Unscheduled candidates:

- Image was 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). Slice 18 dropped the Claude CLI (1.07GB built locally on arm64, 2026-09-19; not measured on the x86_64 deploy build). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. The cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings. Slice 14 needs this, not just wants it: a follow-up like "what about the second one?" has no content words, so the OR-query returns nothing.
