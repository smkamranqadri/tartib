# Slice 24: presentation

Planned and built 2026-09-20, committed just after midnight on 2026-09-21, straight after
slice 23 closed. This is the presentation half of backlog
entry 13, whose themes half was closed the same day and must not be re-opened.

Slice 23 made the whole app monospace at 14px and left one question it could not answer headless:
**whether mono at 14px is comfortable for a long note on a phone.** It was taken knowingly
against readability. Markdown is the strongest answer available short of a device -- a wall of
uniform mono becomes headings, lists and emphasis, which is what makes length readable at any
size. That is why this slice comes next rather than 14.

The entry's own words: markdown on the item page, note bodies and briefs, **rendered and edited
in the same place** -- no edit mode to enter, no button to enter it, the text styles as you type,
and the stored bytes are never rewritten.

## Settled before this plan, and not re-argued

Decided 2026-09-20 while planning slice 23:

- The editor **is** CodeMirror, lazy-loaded (`@uiw/react-codemirror` with
  `@codemirror/lang-markdown`). The lighter overlay the entry used to ask for was costed and
  fails on a hard limit rather than a preference: a transparent textarea over a styled mirror can
  change a token's colour but not its size or weight, because the caret comes from the textarea's
  own uniform metrics. A heading drawn larger in the mirror puts the caret where the text is not.
- `marked` parses the read-only places.
- Markdown reaches item text, the space brief, Ask answers and the thought log.

## Decided with the owner, 2026-09-20

- **Render first, swap on tap.** The item page paints rendered markdown immediately; CodeMirror's
  chunk fetches only when you tap into the text, and the caret lands where you tapped. Reading a
  note on a phone never pays for the editor. The alternative -- the page *is* a CodeMirror
  document from the moment it opens -- has no swap seam, but charges every note you merely read
  150 to 250KB on the surface slice 22 just made primary.
- **The row title stays a link. That sub-item is dropped.** Backlog 13 asked for the title to
  stop being a link so it could be selected and copied, keeping the pencil instead. That was
  decided on 2026-09-17, before slices 21 and 22 existed. On a phone the row *is* the tap target
  that opens the sheet, and long-press to select fights tap-to-open. Trading the primary gesture
  for a rare one is the wrong way round. The pencil stays exactly as it is
  (`ItemRow.tsx:135`); copying a title is solved on the item page, where the text is selectable
  next to a real editor.
- **CodeMirror on item text only.** Thought entries and captures render markdown but compose in
  the plain textarea they already have. A thought is a short dated line, and a capture must never
  wait (rule 2); neither earns an editor, and neither should pull that chunk.
- **Row headlines are flattened.** A note starting with `# Groceries` reads `Groceries` in a
  list. A regex on the first line only -- `#`, `*`, backticks, `>`, link brackets -- no rendering
  and no `marked` on a row. Rows are one dense line and the syntax is noise there.
- **A search hit stays marked, inside rendered markdown.** Slice 20 built "search that lands on
  the line" and named markdown bodies as the reason it would matter. It would be perverse for
  markdown to be what takes it away.
- **Debounced autosave, about 2s after you stop typing.** Chosen over a SAVE pill that appears
  when the text is dirty. See Risk: this is the decision in this slice with the most consequence,
  and three things in the build exist to make it safe.

## The one design decision that resolves two problems

**Do not render `marked`'s HTML output through `dangerouslySetInnerHTML`.** Take the token stream
from `marked.lexer()` and emit React elements from it.

This was reached while planning the search-hit question, and it turns out to settle two things at
once:

- **Nothing can inject.** Raw HTML in the source renders as visible text because no HTML string
  ever reaches the DOM. This matters more than it looks: the space brief and Ask answers are
  written by the model, so rendering them as HTML would be rendering model output as markup.
  Marked has had no `sanitize` option since v5, so the alternative is a second dependency doing
  what emitting our own elements does for free.
- **Highlighting becomes a render branch, not a tree walk.** Because every text node is emitted
  by our own code, wrapping the search terms is something the renderer does as it goes.
  `Highlight.tsx` is reused, not replaced.

Where a token type is awkward, that token falls back to rendering its own raw text. It never
falls back to innerHTML.

## Phase A -- render

1. **`frontend/src/markdown.ts`** -- `flattenFirstLine()`, the headline regex. No dependency.
2. **`frontend/src/components/Markdown.tsx`** -- the token stream emitted as React elements,
   taking an optional search query and wrapping matches through `Highlight`.
3. **The four surfaces.** `ItemPage.tsx:191` (today `<Highlight text={item.raw_text} …>`),
   `Thoughts.tsx:46` (`<p>{t.body}</p>`), `AnswerView.tsx:16` (`<p>{result.answer}</p>`), and the
   brief strip in `screens/layouts/Panes.tsx`.
4. **`ItemRow.tsx:49`** -- `headline` takes the flattening.
5. **`styles.css`** -- the markdown block scale, cut for mono the way slice 23 cut the type
   scale. Headings, lists, code, blockquote and links, all from tokens.

Phase A is shippable on its own. The item page keeps its existing textarea and its existing
explicit save until B replaces them, so nothing is half-built at the boundary.

**Stop here and look at it.** This is the phase boundary, and it is the point where the mono
question gets its best answer short of a device.

## Phase B -- edit

6. **`frontend/src/components/TextEditor.tsx`** -- rendered markdown until you tap it, then
   CodeMirror at the tapped position, lazily. Headings stay heading-sized while you type, which
   is the entire reason the dependency is here rather than a textarea.
7. **Autosave.** Debounced ~2s, and **flushed on blur and on navigating away** -- without that, a
   2s pause before you tap Back silently loses your last sentence.
8. **The save state.** "Saving… / Saved / Not saved", plainly. An explicit button gave this away
   for free and autosave takes it back: `offline.ts` holds one store, `pending-captures`, so an
   edit has nowhere to wait and an autosave offline simply fails. It must say so rather than
   lie. Offline edit queueing is its own backlog item and is not smuggled in here.
9. **The 409, made safe.** Slice 19 refuses a stale save (`items.py:186`) and `ItemPage.tsx:86`
   handles it with Reload or Overwrite at lines 203 and 206. Under autosave that flow needs three
   changes: the 409 shows a **non-modal strip** above the editor rather than a dialog; **your
   local text is never touched** by it; and a successful save **advances `expected_updated_at`
   from the response**, or every save after the first 409 fails in a loop.

## Verification

`playwright-core` on channel chrome against the local container, the way slice 23 was proved:
Home, Inbox, Spaces, a space, an item and Settings at 390px and 1280px. Measured, not assumed:

**Phase A**

- A note with headings, lists, emphasis, code and a link renders as those things on the item
  page, in the brief, in an Ask answer and in a thought entry.
- Raw HTML stored in a real note renders as visible text, never as an element. Proved with an
  `<img onerror>` and a `<script>`, stored as item text and read back.
- A row for a note starting with `# Groceries` reads `Groceries`.
- A search hit still opens scrolled to the line **with the match marked**, now inside rendered
  markdown. Slice 20's behaviour, unchanged from the user's side.
- Row height and the 44px phone floor unchanged from slice 23; no horizontal scroll at 390px.

**Phase B**

- Tapping the text gives a caret at the tapped position, and a heading stays heading-sized while
  being typed.
- The cold item page ships **no CodeMirror**, read off the network list rather than assumed.
- Stop typing, "Saving…" then "Saved"; reload and the text is there.
- Navigate away inside the debounce window; nothing is lost.
- The same item open in two contexts: the second gets the strip, its text is intact, Reload and
  Overwrite each do what they say, and neither loops.
- Offline, the state reads "Not saved".

Then `npm run typecheck && npm run build`, and `uv run pytest -q` as a regression check --
expect **193 passed, 2 deselected**, since this slice touches no backend.

## Risk

**Autosave was chosen over a save button, against the recommendation, and the risk is named
here rather than argued again.** A 2s debounce plus slice 19's stale check means a conflict can
land mid-paragraph. Steps 7 to 9 are what make that livable, and B5 is the check that proves it.
If two-context editing turns out ugly on real use, the fallback is the SAVE pill that appears
only when the text is dirty -- it satisfies the entry's wording just as well, because what 13
banned is a button to *enter* editing, not a button to commit.

**Every autosave bumps `items.updated_at`.** That feeds "last touched" on the space cards slice
23 built and the 14-day stale check the Inbox shows. Opening a note and typing one character
marks it freshly touched. Semantically it is true -- you did touch it -- and it is accepted and
recorded rather than mitigated.

**CodeMirror is the largest dependency this project has ever taken.** `package.json` carries
three runtime dependencies today: react, react-dom, react-router-dom. Lazy loading is the only
reason this is acceptable, which is exactly what the cold-page network check exists to prove. It
is build-time only, so the 1.62GB image is unaffected beyond the built bundle.

**The service worker precaches the shell, and whether CodeMirror's chunk joins it is a real
choice.** In, and an offline launch can edit but the shell grows. Out, and tapping text offline
does nothing. **Recommend out**, with the editor saying so -- which is the same sentence step 8
already has to write.

**Mono at 14px on a phone is still unproved on glass.** Phase A is the strongest answer available
without a device. It is still not a device.


---

## Phase A — what was built, and what it cost (2026-09-20)

**All five steps done and proved in the browser. Phase B not started.**

**`markdown.ts`.** `flattenFirstLine()`, `decodeEntities()` and `safeHref()`. No dependency, no
marked: a row must not pay for a parser.

**`Markdown.tsx`.** marked's token stream emitted as React elements. The decision that no HTML
string is ever built held up and paid for itself twice, exactly as planned -- raw HTML cannot
become an element, and marking the search terms is a branch in the renderer rather than a walk
over someone else's output.

**Four surfaces took it**: the item body (`ItemPage.tsx`), thought entries (`Thoughts.tsx`), Ask
answers (`AnswerView.tsx`) and the space brief (`Panes.tsx`).

**Five places compute a row headline, not one.** The plan named `ItemRow.tsx:49`. A grep found
the same first-line logic in `screens/layouts/shared.tsx`, `RecentList.tsx`, `SessionBar.tsx` and
the citation line in `AnswerView.tsx`. Flattening one of five would have left four rows showing
`#`, so all five call `flattenFirstLine` now and the rule lives once.

**Two things found by building it that the plan did not know:**

- **`marked` defaults to `breaks: false`, and that would have silently reflowed every note in
  the database.** Notes here are typed, not authored: a line ends and another begins, and the old
  `.raw` was `white-space: pre-wrap`, so that is how every existing note looks. With marked's
  default a single newline is a space, so on the day this shipped every such note would have
  collapsed into one block. `breaks: true`, deliberately, with the reason in the code.
- **`marked` emits a `checkbox` token first in a task item, and its raw text is the literal
  `[ ] `.** The first render showed a checkbox *and* `[ ]` beside it. Caught by looking at the
  screenshot, not by a passing assertion -- every check was green at the time. The token is
  dropped; the box is drawn from the item's own `task`/`checked`. There is now a check for it.

**Deliberately left plain**, both showing captured bytes rather than a document: the original
capture on the item page (`ItemPage.tsx`, the "original differs" block) and the decision card
(`ApprovalCard.tsx`). Rendering either would change what they are for.

### Verification — what actually ran

`playwright-core` on channel chrome against the local container, **32 checks, all passing**:

| | |
|---|---|
| A1 | headings, lists, emphasis, code, blockquote, table, task boxes, a link with its words, and a single newline surviving as a break |
| A1 | task items carry no literal `[ ]` (the defect above, now guarded) |
| A2 | `<img src=x onerror=…>` and `<script>` stored as real item text produce **no element and no execution**, and appear as characters; `[evil link](javascript:…)` keeps its words and has no href; `&amp;`/`&lt;` decode |
| A3 | a row for a note starting `# Slice 24 proof` reads `Slice 24 proof` |
| A4 | a search hit still opens marked, now inside rendered markdown (`.md mark.hit`) |
| A5 | Home, Inbox, Spaces, Settings and an item at 390px: every control clears 44px, no horizontal scroll on any |
| | no page errors after login (the unauthenticated first load 401s by design, and that is asserted separately rather than ignored) |

Looked at, not just asserted: the item at 1280 and 390, and the rendered block on its own.
Prose links inside `.md` are exempted from the 44px rule and the exemption is explicit in the
harness -- an inline link in a paragraph is text, not a control.

`npm run typecheck` and `npm run build` clean. `uv run pytest -q` -- **193 passed, 2 deselected**,
unchanged; no backend was touched.

**Cost:** the bundle went to 393.23 kB / **122.39 kB gzip**, about +12 kB gzip for `marked`.
That is Phase A's entire weight, and it is the reason the editor is Phase B and lazy.

### Still open for Phase A

Whether mono at 14px with markdown is comfortable for a long note **on a device**. Phase A is the
strongest answer available headless. It is still not a phone.


---

## Phase B — what was built, and the three things it got wrong first (2026-09-20)

**All four steps done and proved. 32 browser checks, green three runs running.**

**`MarkdownEditor.tsx`** is the whole of CodeMirror and nothing else imports it, so it is its own
chunk. **`TextEditor.tsx`** owns the swap, the draft, the debounce and the save state.
`ItemPage.tsx` lost its edit mode, its textarea and its **Edit button** -- what backlog 13 asked
for: there is no mode to enter and no button to enter it. Tapping the words is the gesture.

**The cost, measured:** the cold item page is **124.33 kB gzip**, up 1.16 kB from Phase A. The
editor is a separate **213.86 kB gzip** chunk that a note you only read never fetches -- proved
from the request list, not assumed. `index.html` does not name it, which also means `sw.js` does
not precache it, which is what the plan recommended.

### Three things that were wrong, and what they cost to find

**1. Mapping the tap by coordinates does not work, and cannot.** `posAtCoords` was asked for the
position under the tapped point. It answered from the top of the document, so every edit landed
at **offset 0** -- and because the autosave then saved it, the test document filled up with text
accumulating at the front. Waiting for a measure moved the answer from "line 2" to "offset 0",
which is the tell: the rendered markdown and the source do not share a layout, so a point in one
is not a point in the other, and no amount of measuring fixes that.
It maps by **word** now: the tap records the Nth occurrence of the word it landed on, and the
editor finds that word again in the source. Words survive rendering because markdown syntax sits
around them, not inside them. Needs no layout, right on the first frame. Proved: a tap at 62%
of a paragraph puts the caret at offset 84 of 118, on the line that was tapped.

**2. `keepalive` is not a guarantee, and the proof that it is not is on record.** The flush on
the way out is sent with `keepalive: true`, which is correct and demonstrably works in isolation
-- three runs out of three. Inside the full suite it failed every time, and counting the
server's own log lines settled what was happening: **79 PATCH lines before the teardown, 79
after.** Not a 409, not a refusal -- the request never arrived. The browser drops it.
So the promise cannot rest on it. The draft is now also written to `localStorage` as it is
typed and read back on the way in, which makes "nothing is lost" true whether or not the last
request survives: the text comes back, says **Unsaved**, and saves itself on the next touch.
It is cleared the moment the server has it, so nothing stale can resurrect.
This is crash safety, not the offline edit queue in the backlog -- no queue, no replay, no
conflict logic of its own. A restored draft saves through the ordinary path and gets the
ordinary strip if the item moved on.

**3. A React state update before the fetch can cost you the fetch.** `flush` set "Saving…" and
then sent the request. On the way out of a page that order loses the edit: the state update
defers the call past the point where the renderer is gone. The request goes first now, the
state second.

### The conflict, which is the reason the owner's choice needed care

Autosave plus slice 19's stale check means a refusal can land mid-paragraph. It does not open a
dialog. A strip appears above the text -- *"Changed elsewhere since you opened it. Your text is
kept."* -- with Reload and Overwrite, the words stay exactly where they are, and the editor goes
on saying **Unsaved**, because that is what is true of them. The debounce is **paused** while it
is unresolved, so nothing retries into the same 409 every two seconds.

One bug here was only visible because the whole flow was tested: resolving a conflict remounts
the editor, and **the old instance flushed on its way out**, sending the held draft again,
409ing again, and putting the strip straight back up -- undoing the choice just made. A flush is
now skipped while blocked.

### Verification — what actually ran

`playwright-core` on channel chrome against the local container. **32/32, three consecutive runs.**

| | |
|---|---|
| B1 | a tap fetches the chunk, focuses, and puts the caret on the tapped line at offset 84 of 118; a heading measures **23.4px against 18px body while being typed**, with `# ` visible and recessed |
| B2 | the cold page fetches **no** editor chunk, and there is no Edit button |
| B3 | type, pause, "Saving…" then "Saved"; the server has it; it survives a reload |
| B4a | in-app navigation inside the debounce window still saves |
| B4b | a hard teardown loses nothing: the text is there on return, says Unsaved, reaches the server on the next touch, and the local draft is cleared once it does |
| B5 | two contexts on one item: a strip not a dialog, the local text kept, still Unsaved, **no retry loop** (`updated_at` unchanged over 5s), Overwrite sends the held edit and clears the strip, Reload takes the server's copy |
| B6 | offline says **"Not saved · offline"** and the typed text stays |
| | the phone at 390px while editing: 44px targets, no horizontal scroll |

Looked at: the editor at 1280 and 390, and the conflict strip. `npm run typecheck` and
`npm run build` clean; `uv run pytest -q` **193 passed, 2 deselected**, unchanged.
Phase A's 32 checks re-run green after all of this.

### Still open

Mono at 14px with markdown, on a device. Unchanged by Phase B, and still the one thing that
needs glass.
