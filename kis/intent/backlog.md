# Backlog

Approved work waiting for a plan, then defects, then candidates that are not required and may
never happen. How Tartib is built lives in `../knowledge/technical.md`.

Slices 15, 16 and 17 -- PWA, public repo, deploy -- were put ahead of everything here on
2026-09-18 and all closed that day; their plans stay in `slice-1{5,6,7}-*.md`. Nothing below is
ordered yet.

Approved on 2026-09-17, not yet planned. Each gets a plan file when it comes up:

- **13 presentation** — markdown on the item page, note bodies and briefs, rendered and edited
  in the same place: no edit mode to enter and no button to enter it, the text styles as you type,
  and the stored bytes are never rewritten.
  Six themes in Settings -- slate, bronze and nous, each in light and dark, with slate dark the
  default, the current teal pair dropped, and no OS-following. The palettes, the token mapping and
  the measured contrast are recorded as data in `themes.md`.
  The row keeps its pencil and the title stops being a link instead. This reverses the
  2026-09-17 decision to delete the pencil: it was redundant because the title went to the same
  place, but a title that is a link cannot be selected and copied, and copying the title is worth
  more than losing the duplicate control. The pencil is the `aria-label="Edit"` link in
  `frontend/src/components/ItemRow.tsx`, line 93 on 2026-09-19; line numbers drift.
  A CodeMirror editor (`@uiw/react-codemirror`, with the theme and the lazy grammar in a shared
  module) is a proven route for the live editor and should be costed at plan time against a
  lighter overlay. It is a new frontend dependency in an app with a 512MB budget, so this entry
  records it as the known option and does not choose it.
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

Slice 19 (`slice-19-small-items-2.md`, planned 2026-09-19) takes: failed-capture retry (from the
candidates), proposed due dates, "Say why an item needs you", Inbox tabs, the session-end ring,
and "Refuse a stale save". Those leave this file when it closes. Dropped the same day: "a
notification key that cannot fire twice" -- all three pushers already hold a once-only guard
(`reminded_at`, `digest_date`, `notified_at`).

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
- **A ring when a session ends**, the way Pomofocus does it. This needs no change to rule 4: the
  session-end push is already the third allowed pusher, and a sound is not a fourth one. Most of
  it is in-page audio from the running tab rather than the notification, because a web push
  cannot carry a custom sound. It would also cover a known gap: today the service worker shows
  nothing when a session ends with the app on screen, so a ring is the honest signal for exactly
  that case.
- **An item graph.** Notes and tasks as nodes, the links between them as edges, clustered by
  space and sized by how often an item is referenced. This is the whole point of linking, and it
  is blocked on "Link, don't duplicate" above: with no links there are no edges and the graph is
  a scatter of unconnected dots. A deterministic force layout drawn as plain SVG is enough, so
  this needs no charting or graph dependency.
- **Refuse a stale save instead of overwriting it.** An item edit carries the timestamp the
  editor loaded, and the server rejects a write whose timestamp is behind the stored one rather
  than taking it; the UI then offers Reload or Overwrite. One user is not one device: an item
  left open on the phone while the desktop edits it loses one of the two edits today, with
  nothing said. This gets worse with 13, because live editing means items stay open.
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
- **Say why an item needs you.** An item waits in Needs Attention for at least four different
  reasons -- confidence under the threshold, no space matched, the AI call failed
  (`proposal_error`), or a task has gone 14 days stale -- and all four look identical on the card.
  Each item should carry its cause. It pairs with the two entries above: the cause is what tells
  you whether to answer a question, edit the proposal, or send it back with a reason.
- **A filing policy per space.** A column on `spaces` that overrides the confidence rule in both
  directions: a space that never auto-files and always asks, and a space that always auto-files
  whatever the confidence. Today one global 0.85 threshold decides everything. A rule the database
  enforces, not an instruction in a prompt -- a prompt can be ignored, and elsewhere this exact
  gate exists because the prose version was ignored once.
- **Offline read, and offline edit.** The app goes blank of data the moment the network does.
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
  editable since 2026-09-17. A queue of offline edits lands exactly on "Refuse a stale save"
  above; plan the two together or the second one will fight the first.
  Keep classification on the server when this is built. An earlier build let each device classify
  what it had queued, and one capture became a note on the laptop and a task on the phone at the
  same time. Tartib's runner is already the only classifier; an offline queue must replay raw
  captures and edits to it, never decide anything locally.
- **UI polish, phone first.** Two specifics, independent of each other (safe areas and the nav surface shipped in slice 18):
  *Skeleton rows* -- every card shows a bare `...` while it loads and then jumps when data lands;
  placeholder rows in the shape of the content hold the layout still.
  *Typography and controls* -- one bundled sans and one bundled mono, self-hosted with no CDN so
  the app looks the same on every device and still works offline; one button scale; the nav pill
  bar reserving its own height so nothing hides behind it (the top nav is sticky since slice 18, the ask bar was already fixed); background colour coming from the theme
  tokens rather than per-screen values.
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
- **Inbox becomes tabs, not a vertical stack.** Needs attention, Stale tasks and Recent are three
  cards stacked down one screen, so the lower two are a scroll away and the counts are invisible
  until you reach them. One tab strip with the count on each tab, one section at a time. Two
  routes already exist from slice 10, `/inbox/attention` and `/inbox/recent`, so decide whether
  the tabs *are* those routes or replace them -- do not end up with both. Slice 18 already keeps
  waiting items out of Recent -- server side on `/inbox/recent`, client side on the Inbox card --
  so the tabs inherit that rather than rebuilding it.
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
- **Propose a due date for a task that names none.** The classifier returns `due: null` when the
  text has no date, so "follow up with the dentist" is filed undated and never reaches Today --
  the one screen built to surface it. Propose a near-term date instead: a day or two for
  time-sensitive follow-ups and errands, up to a week for lower-urgency ones, relative to now. An
  explicit date in the text always wins, and notes stay undated unless a date is named. A prompt
  change only; the field already exists. The failure to watch for is the opposite one -- Today
  filling with dates you never chose -- so the eval fixtures need dateless tasks that should stay
  undated as well as ones that should not.
- **Backups for the deployed database.** Slice 17 step 4 called for a cron copying
  `/data/tartib.db` off the persistent directory and one restore actually performed; deferred
  2026-09-18. CapRover's persistent directory is the same disk as the rest of the host, so it is
  not a backup, and everything in that database exists exactly once.

Unscheduled candidates:

- Image was 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). Slice 18 dropped the Claude CLI (1.07GB built locally on arm64, 2026-09-19; not measured on the x86_64 deploy build). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- Automatic retry for `proposal_error` items after a Codex outage or usage-limit block. Today they wait for a human, or for `python -m tartib.reclassify --attention`. Worth more since slice 18 removed the Claude fallback: Codex is now the only classifier, so every outage parks captures. Seen for real on 2026-09-17 when the ChatGPT usage limit hit mid-deploy.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. The cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings. Slice 14 needs this, not just wants it: a follow-up like "what about the second one?" has no content words, so the OR-query returns nothing.
