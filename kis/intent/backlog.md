# Backlog

Approved work waiting for a plan, then defects, then candidates that are not required and may
never happen. How Tartib is built lives in `../knowledge/technical.md`.

Slices 18 to 25 (2026-09-19 to -21) took most of what used to be here -- the defects, the small
items, the session card, the space page, the phone layout, the typography, markdown with its
editor, and offline -- and each left its proof in its plan file. Eight entries that slice 20
shipped on 2026-09-19 sat here until 2026-09-21 before anyone noticed. What is below is what is
actually left, and nothing in it is ordered yet.

Approved on 2026-09-17, not yet planned. Each gets a plan file when it comes up:

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

Slice 20 closed on 2026-09-19 and its eight entries left this file on 2026-09-21, later than
they should have: add directly, filing policy per space, skeleton rows, search landing on the
matched line, the session card, the space page split view, tell it why, and the thought log.
What each one became is in `history.md`; what is true of them now is in `../knowledge/`.

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
- **The classifier may propose a space that does not exist yet.** A proposal only: naming it does
  nothing, and accepting it is what creates the space. An unaccepted proposal leaves the item
  where an unknown space leaves it today, at null with confidence capped. Decided 2026-09-19. Rule
  7 says the classifier never invents a space, and it says that because a classifier free to
  invent sprays one-off spaces across the database; this narrows the rule rather than dropping it,
  and the wording needs updating when it ships.
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

Unscheduled candidates:

- Image was 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). Slice 18 dropped the Claude CLI (1.07GB built locally on arm64, 2026-09-19; not measured on the x86_64 deploy build). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. The cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings. Slice 14 needs this, not just wants it: a follow-up like "what about the second one?" has no content words, so the OR-query returns nothing.
