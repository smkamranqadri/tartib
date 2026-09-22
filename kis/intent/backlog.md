# Backlog

Approved work waiting for a plan, then defects, then candidates that are not required and may
never happen. How Tartib is built lives in `../knowledge/technical.md`.

Slices 18 to 26 (2026-09-19 to -21) took most of what used to be here -- the defects, the small
items, the session card, the space page, the phone layout, the typography, markdown with its
editor, offline, and retrieval -- and each left its proof in its plan file. Eight entries that slice 20
shipped on 2026-09-19 sat here until 2026-09-21 before anyone noticed. What is below is what is
actually left, and nothing in it is ordered yet.

Approved on 2026-09-17, not yet planned. Each gets a plan file when it comes up:

- ~~**14 AI contract**~~ — **built in slice 27** (2026-09-21), and not yet closed: one prompt
  change in it is unmeasured. See `slice-27-ai-contract.md`, Still open. What shipped: house
  rules appended to the prompt rather than replacing it, the classifier asking which space
  instead of guessing, and corrections as few-shot examples. What did **not**: Ask becoming
  continuous beyond slice 26's single turn, and multiple-choice answers, which have no field to
  land in here. The original entry, for the record:
  the classifier prompt editable and stored as an override with the
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
rather than work beside it.

"One set of shared rules across both prompts" **closed with slice 26** (2026-09-21). It was
never as bad as this file claimed -- the two prompts shared three lines, and `format_item` only
ever existed once, because classify saw no items to format. Slice 26 is what would have created
the duplication, so it took `store.item_header` as the one owner of what an item looks like to
the AI, and both prompts use it.

Deferred from a slice rather than never planned:

- ~~**Link, don't duplicate**~~ — **done in slice 28** (closed 2026-09-22),
  `slice-28-what-the-classifier-may-name.md`. The classifier should attach a capture to an item
  that already exists instead of filing a near-duplicate beside it.
  **Correction (2026-09-21):** this entry used to claim slice 26 shipped its retrieval half.
  Half true, and the wrong half. `store.classify_context` is context about the *database* --
  per-space counts and recent items -- and takes no capture text at all. Duplicate detection
  needs the items that resemble *this capture*, which is a per-capture search, and that is part
  of slice 28.
  This is proven, not speculative, and now proven here: on an earlier build, real context from
  the database took discriminating cases from 1/6 to 5/6; **slice 26 measured 0/6 to 6/6 on this
  build** (`slice-26-retrieval.md`). Duplicate detection that *parked* a
  suspected duplicate in review naming the item it matched, rather than filing it or merging it
  silently, caught 3/3 real duplicates with 0/5 false positives and no invented references. Park
  and name the match; do not auto-merge. Build the context server-side, so there is one source of
  truth for what the classifier is shown.
- **AI usage on record** — **built as slice 29** (2026-09-22) and **not closed**:
  `slice-29-ai-usage.md`. `--json` is on for every AI call and has only run against the fake,
  so it is unproven that the reply file is still written with the stream on. The entry stays
  open until that and the token arithmetic are settled. Count the calls and the tokens, per call and in total, and show them.
  **No longer unestablished:** `codex exec --json` emits the turn as JSONL and `turn.completed`
  carries a `usage` object with input, cached input, cache-write input, output, reasoning and
  total tokens. The mechanism and its two traps are in `../knowledge/technical.md`.
  Decided 2026-09-21: **counts plus a costed estimate**, not counts alone. Both CLIs run on a
  subscription and will report no cost, so any money figure is an estimate: price the tokens
  from a model price catalogue fetched at most once a day and cached on disk, keeping the last
  good copy when a fetch fails (models.dev publishes one as JSON, USD per million tokens).
  Counts are the feature; the cost is a derived number and must read as one.
- **An item graph.** Notes and tasks as nodes, the links between them as edges, clustered by
  space and sized by how often an item is referenced. This is the whole point of linking, and it
  is unblocked now that slice 28 has shipped linking: with no links there are no edges and the graph is
  a scatter of unconnected dots. A deterministic force layout drawn as plain SVG is enough, so
  this needs no charting or graph dependency.
- ~~**The classifier may propose a space that does not exist yet**~~ — **done in slice 28**
  (2026-09-21), beside park-and-name, because both are a proposal naming something outside its
  own fields. A proposal only: naming it does
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
- ~~Ask retrieval is keyword-only FTS5.~~ **Done in slice 26** (2026-09-21): when the question's
  own words find little or nothing, Codex proposes 3 to 5 terms and retrieval runs again. Still no
  embeddings. Its worked example turned out to need the other half of that slice -- "what about the
  second one?" refers to the previous answer, which no amount of term expansion can reach, so Ask
  now carries one turn. Continuous Ask remains 14's.
