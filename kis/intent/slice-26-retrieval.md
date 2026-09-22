# Slice 26: retrieval

Planned 2026-09-21, after slice 25 closed. This is the retrieval half of backlog 14, carved out
and done first, plus the two backlog entries that fall out of doing it: "one set of shared rules
across both prompts" and the unscheduled "Ask retrieval is keyword-only FTS5".

Both prompts are starved of context in the same way, and neither knows it. `classify` is shown
the datetime and a flat list of space *names* (`classify.py`, the `Existing spaces:` line) -- it
never sees a single item, so it cannot tell that "the Thursday call" belongs where six months of
similar items already live. `ask` sees items, but only the ones an OR of the question's own
content words happens to match (`retrieval_query`, `ask.py`), so a question phrased in words the
notes do not use finds nothing and falls through to the twenty most recent items.

Slice 14 assumes both are fixed. The editable prompt override, the classifier asking you a
question, and corrections-as-examples are all prompt work layered on a context that does not
exist yet. Building the context first makes 14 a prompt slice instead of a prompt-and-retrieval
slice.

## Decided with the owner, 2026-09-21

- **Retrieval alone, then 14.** Offered against taking 14 whole, against a small round of
  leftovers, and against the classifier proposing new spaces. Retrieval won because the other
  three sit on top of it.
- **One deploy after, not before.** Slices 23, 24 and 25 have never been seen on a device.
  Offered shipping `v1.1` first to settle that; declined. 23 to 26 go out together in one
  `v1.1`, and the device pass covers all four at once. This is the size risk: see Risk.
- **The single-turn carry is in.** See "What the repository says" below -- without it, the
  backlog's own worked example stays broken.
- **Shared prompt rules ride along.** This slice is what creates the duplication, so it owns it
  from the start rather than leaving 14 to unpick two copies.
- **The UI harness is committed as a suite, this slice.** Every slice so far has built one in
  the scratchpad and binned it. That is how slice 24's conflict strip reached a phone 430px wide
  unchecked: its own harness never had a conflict on screen, and slice 25's was the first thing
  able to look. Because 23 to 25 now ship *with* this slice, a suite that can re-run their checks
  is load-bearing for the release rather than decoration.

## What the repository says that the backlog does not

Checked on 2026-09-21 before planning. Line numbers drift; the names do not.

**The backlog's own example is not fixed by the backlog's own fix.** It argues for term
expansion because *"a follow-up like 'what about the second one?' has no content words, so the
OR-query returns nothing."* The first half is true -- `retrieval_query` drops stopwords and ORs
the rest. The second half is not the whole cause: "the second one" refers to the *previous
answer's* item list, and `answer_question` keeps nothing between turns. No expansion can resolve
it. Expansion fixes thin questions; the carry fixes that one. Hence the decision above.

**The shared-rules entry overstates today and understates tomorrow.** It says both prompts carry
their own copy of "the item header format and the datetime handling". Today the shared text is
three lines -- `Reply with one JSON object only`, `Do not run commands or read files`, and
`Current datetime: {now} ({zone})` -- and `format_item` exists once, in `ask.py`, because
classify never sees items. Extracting that today would be premature. The duplication it warns
about arrives the moment classify is shown items, which is step 2 of this slice.

**The eval cannot currently measure what this slice is for.** `tests/test_eval.py` builds
`Context` with a flat `SPACES` list and no database at all. The 1/6 to 5/6 figure in the backlog
is from an earlier build of the same idea, not from this one. Either this slice re-measures it
on discriminating fixtures or it does not get to claim it.

**Two Codex calls cost what two Codex calls cost.** Roughly 10s each on the deployed host, and
they are serial subprocesses. Always-expanding doubles every question. `retrieve` already returns
`matched=False` when it falls through to the most-recent branch, so the expensive path can be
spent only where the cheap one failed.

## The limit, stated rather than hidden

**This slice makes the classifier better informed, not better armed.** It will choose spaces
better because it can see what already lives in them, and that is measurable. It still cannot
say "this is the same thing as item 41" -- naming an item to attach to needs a field the
proposal schema does not have. Park-and-name stays in 14, where the schema changes. Anyone
reading this later should not expect duplicate detection to have shipped here.

## Steps

1. **The context builder, in `store.py`.** One function, server-side, so there is one source of
   truth for what the classifier is shown: each space with its counts and a bounded list of
   recent item titles. Titles and counts, never raw item text. A stated character budget,
   asserted in a test against a full database. Both construction sites -- `runner.py` and
   `items.py`, the retry path -- feed from it.
2. **`classify.py` consumes it.** `Context` gains the built context; the prompt gains a bounded
   context block; the item header format moves to one shared formatter that `ask.py` uses too,
   closing the shared-rules entry as a side effect.
3. **`ask.py` expands, conditionally.** When the FTS path fails or returns almost nothing
   (`not matched or len(rows) < 3`, tunable), one Codex call proposes 3 to 5 search terms and
   retrieval runs again on them. A question that already works makes exactly one call, as today.
4. **`ask.py` carries one turn.** The prior question and the `item_ids` it returned, seeded into
   the candidate rows. No schema change; the client already holds the last answer. This is a
   deliberate toe over the line into 14's continuous Ask -- **14 should extend it, not rebuild
   it.**
5. **The eval learns to discriminate.** Fixtures where the space names alone are ambiguous and
   the existing items settle it, run with and without the context. Both numbers recorded here.
6. **The UI suite, committed.** Under `frontend/tools/`, which already exists for committed
   tooling and already has a gitignored `out/` and a precedent -- `themes.py` writes
   `expected.json` "for the proof harness". Scoped to re-running slices 23, 24 and 25's checks,
   not a general framework. Last, so it cannot delay the retrieval work.

## Verification

- A question whose words match nothing today returns the right items after expansion, and the
  same question with expansion disabled returns none. Both asserted.
- A question that already matches makes **exactly one** Codex call. Asserted on the fake.
- "what about the second one?" after a prior answer resolves to that answer's second item.
- Discriminating eval fixtures: space accuracy with the context beats the flat-list baseline.
  Both numbers written into this file when they are known. The existing 22 fixtures do not
  regress.
- The classify prompt stays under the stated budget with a full database.
- The committed suite re-runs 23 to 25's checks green against the local container before `v1.1`
  is tagged.
- `cd backend && uv run pytest -q` (193 passed today, plus whatever this adds) and
  `uv run pytest -m eval`. `cd frontend && npm run typecheck && npm run build`.

## Risk

**Four unanswered visual questions are still open while this is built.** Whether mono at 14px
suits a long note, whether `background-attachment: fixed` survives iOS, whether tapping a word
is a discoverable way into editing, and whether a debounced autosave feels safe without a Save
button. By the owner's decision they wait for one `v1.1` covering 23 to 26. If any of them is
wrong, the fix arrives four slices late. The committed suite in step 6 is the partial answer --
it cannot judge whether mono at 14px reads well, but it can stop 23 to 25 regressing while
26 is built on top of them.

**Two serial Codex calls mean ~20s on a failed question.** Mitigated by the conditional trigger.
If it still feels bad on the phone, the trigger tightens; the feature does not go away.

**A longer classify prompt slows every capture**, and captures queue serially at ~10s. Budgeted
in step 1 and measured, not assumed.

**Step 6 is a second deliverable in a backend slice.** Sequenced last for that reason.

## What was built (2026-09-21)

All six steps. Three things the plan did not foresee, each found by the step that came after it.

### The context said nothing about notes

Step 1 built the context out of `item_header`, the format shared with ask. Step 5 then tried to
write fixtures against it and could not: a task's header carries its title, but a **note's header
is `[id 5] 2026-09-20 · space: home · note`** -- space, shape, date, and no content whatsoever.
Ask gets away with it because the item's text follows underneath. The classifier was being shown
a list of dates.

So `context_line` adds `CONTEXT_EXCERPT` (60) characters of a note's first line. That reverses
the plan's "headers only, never an item's text", and deliberately: the reason for that rule was
prompt budget, and 60 characters keeps the budget while making half the database visible at all.
The shared header is still one function; the excerpt sits on top of it for classify only.

### The expansion guard blocked the case it was built for

Step 3 first asked "is there anything beyond what retrieval returned?", counting the returned
rows. But when nothing matches, `retrieve` returns *the most recent items*, not answers. On a
small database that is the whole corpus, so the guard concluded there was nothing left to find
and skipped expansion -- exactly when expansion was the only thing that could help. It now counts
**matched** rows, which is 0 in that case. The test that caught it was an existing one: a capture
that is a question, in a database holding one item, suddenly cost two Codex calls.

### `expanded` means the terms changed the answer, not that a call was made

Proved against the real database: *"what is my cardio routine?"* expands to running, treadmill,
cycling, workout, exercise -- and still finds nothing, because there is nothing. The flag reads
False there. It is about the result, not the spend.

### Also, one defect the committed suite caught on its first run

`.sentence .word` had `min-height: 44px` on a phone and no `min-width`, so the **Note** and
**Task** buttons in the Inbox decision row were 44 tall and **38 wide**. Slice 23 work, found in
slice 26, fixed here in one line because it would otherwise have shipped in `v1.1`. This is the
whole argument for step 6, made on the day the suite was written.

## Verification -- what actually ran

**The measurement (step 5), against the real Codex CLI:**

| | space names only | with what already exists |
|---|---|---|
| 6 discriminating captures | **0/6** | **6/6** |

Nothing was near-missed: blind, it answered work, finance, work and then three nulls. The
existing 22 classify fixtures and the 3 tell-it-why cases are unchanged and green, so the context
did not buy this by breaking something else. `uv run pytest -m eval` -- **3 passed**, 64s.

**End to end on the local container, with the real Codex CLI, not the fake:**

- *"what do I owe the university?"* -- neither word appears anywhere in that database. Expansion
  proposed terms, retrieval found the tuition task, the answer cited item 49 and was correct.
  `matched: true, expanded: true`, 14.3s for both calls.
- *"what about the second one?"*, carrying the prior question and its item ids, correctly
  answered that the previous answer had listed only one. The referent reached the model.
- The same follow-up against a **multi-item** prior answer was not run live: the Codex
  subscription hit its usage limit mid-session. The error surfaced as a clean 502 rather than a
  hang. `test_follow_up_resolves_against_the_previous_answer` covers that case, asserting the
  second of three and the order the items reach the prompt in.

**The committed UI suite (step 6)**, `npm run ui` against the local container, 390px, real Chrome:

| | |
|---|---|
| S23 | body text 14.77:1 and muted text 5.61:1 on the surfaces they actually sit on |
| S22 | no horizontal scroll on Home, Inbox, Spaces or an item |
| S22 | every tap target reaches 44px -- **failing before the fix above** |
| S24 | `**bold**` renders as `<strong>`, not asterisks |
| S24 | tapping the text opens the editor (via `dispatchEvent`, per the knowledge note) |
| S25 | a cold start offline still shows data, and says how old it is |
| S25 | an edit made offline holds and reads "waiting to send" |

**8/8.** It makes its own items through the API and deletes them again; checked afterwards that
the database held none. Two of its own checks were wrong first and are worth recording: one
reported `ok` when it could not find the control it was looking for, and one matched
`aria-label*="tar"`, which "Start session" also satisfies.

`uv run pytest -q` -- **206 passed, 3 deselected**. `npm run typecheck` and `npm run build` clean.

## Still open

- ~~The multi-item live follow-up.~~ **Run 2026-09-22 and it works.** *"what do I review
  daily?"* cited items 42 and 43; *"what about the second one?"*, carrying that pair,
  answered about **43** -- the second of them -- and cited only it. The single-item case was
  proved the day this slice closed; this was the case only a unit test had covered.
- The suite runs against whatever database it is pointed at. It cleans up after itself, but it
  is a check, not a fixture: point it at local.
- **This slice's ask-bar carry is not in the committed UI suite**, and nor is slice 28's
  duplicate line: both need a database row the API cannot create. Recorded in
  `../knowledge/technical.md` beside what the suite does cover, because "slices 22 to 29" read
  as a range and implied otherwise.
- `expanded` is not surfaced anywhere in the UI. `matched` was not either, so this changes
  nothing, but both are now in the payload if a later slice wants them.
