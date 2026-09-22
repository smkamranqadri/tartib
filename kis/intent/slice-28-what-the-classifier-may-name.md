# Slice 28: what the classifier may name

Planned 2026-09-21, after slice 27 closed. Two backlog entries that turn out to be the same
problem wearing different hats: **the classifier can describe things, but it cannot point at
them.** It can say "work", because work is in a list it was given. It cannot say "this is the
same thing as that", and it cannot say "this belongs somewhere that does not exist yet".

Both are a proposal naming something outside its own fields, and both fail the same way if done
carelessly -- the model invents a reference and the server believes it.

## Decided with the owner, 2026-09-21

- **These two together; AI usage on record is slice 29.** Offered as one Phase of three and as
  one-at-a-time. Both of these change the proposal schema, which slice 27 just added `clarify`
  to, so they get one careful pass over the schema, the prompt and the decision UI. Usage shares
  nothing with them.
- **Parking behind `TARTIB_DUPLICATE_PARK`, default off.** The verdict is computed and recorded
  from day one; nothing is held back until it is switched on. Offered parking from day one and
  never-park-only-mark; both declined in favour of running dark first.
- **Ordinals, and the classifier stops being shown real ids.** See below -- this is the decision
  the slice turns on.
- **Costed estimate for slice 29**, not counts alone. Recorded here so it is not re-litigated.

## The correction this slice starts from

**The backlog says link-don't-duplicate's retrieval half shipped in slice 26. It did not -- not
the half this needs.** `store.classify_context(conn)` takes no capture text: it shows per-space
counts and the five most recent items in each. That is context about the *database*. Duplicate
detection needs context about *this capture* -- the items that resemble it.

That retrieval does exist, but it belongs to Ask: `retrieval_query` and `search`, both built in
slice 26. So this is reuse, not new machinery. They move into `store.py`, because classify must
not import from `ask.py`, and Ask imports them back. **Ask's behaviour must not change, and its
tests are what say so.**

## Why ordinals, and not ids

An earlier build settled this with a measurement and the reasoning is worth keeping whole.

Candidates carry a short ordinal in the context. The model returns the ordinal. The server holds
the map and never sends an id. **An invented ordinal maps to nothing and is rejected by
construction** -- no validation rule required, because there is nothing for a wrong answer to
land on.

The alternative is letting the model name a real id and checking it against the set it was shown.
That check is one line, and it fails in exactly the case that matters: a plausible-looking id
that *happens to exist*. Schema validation will not save you either -- it checks types and enums,
so a hallucinated integer is a perfectly valid integer. That build measured **3/3 real duplicates
caught, 0/5 false positives, and 0 refs that resolved to nothing**, and the near misses were the
interesting part: same subject, different action -- "email Sarah the PRD feedback" against an open
"Review Sarah's PRD" -- both correctly came back null.

**This means slice 26's context stops printing `[id 91]`.** Ask still needs ids, because its whole
contract is returning `item_ids` and validating them against the retrieved set. So the single
owner stays single and gains a parameter: `item_header(row, ref)` prints whatever label it is
given -- `id 91` for Ask, `i3` for classify. One function, one format, two labels. Not two
renderings, which is the drift slice 26 closed.

## Steps

**A. Park and name a duplicate.**

1. `retrieval_query` and `search` move from `ask.py` to `store.py`; `ask.py` imports them back.
   Ask's prompt, behaviour and tests are untouched -- that is the acceptance check.
2. `store.item_header(row, ref)` takes the label to print. Ask passes `id {n}`; classify passes
   the ordinal.
3. `store.similar_items(conn, text, limit)` -- the candidates for one capture, with an ordinal
   map that stays on the server.
4. `Context` gains those candidates; the prompt shows them and explains what an ordinal is for.
5. `Proposal` gains `duplicate_of`: one ref, or null. **One field only** -- the server composes
   what the row says from the matched item, because every model-authored field is another thing
   to validate.
6. `_normalize` resolves the ref through the map. Unresolvable means null, silently.
7. Migration **0015**, additive: `items.duplicate_of` and `items.wait_reason`. `attention` now
   has three causes -- no space, low confidence, suspected duplicate -- and a row that cannot say
   which is a row that says nothing. `wait_reason` is a short code, not display text: the client
   already has the matched item and can write the sentence itself.
8. `TARTIB_DUPLICATE_PARK`, default off. Off: the verdict is recorded and filing behaves exactly
   as it does today. On: a suspected duplicate waits instead of filing.
9. `ApprovalCard` says what it looks like -- "Looks like: <title>", linking to that item.
   `waitingReason` learns the new cause.

**B. The classifier may propose a space that does not exist.**

10. `Proposal` gains `new_space`: a name, or null. A proposal only.
11. `_normalize` drops it if it already exists, or if it fails the same name rules the Spaces page
    enforces (lowercase, digits, dashes, 24 max). An item carrying one is treated exactly as an
    item with an unknown space is treated today: null space, confidence capped.
12. `approve` accepts it: creating the space and filing the item there is one act. Not accepting
    leaves the item waiting, and the proposal dies with it.
13. The decision UI shows it as one more option beside the real spaces. It stays a **separate
    field** from `clarify` so the two cannot tangle; the UI may render them together.
14. Rule 7 is narrowed rather than dropped -- it already carries a parenthetical saying this is
    coming, and that parenthetical is replaced by the rule itself.

## Verification

- Seeded duplicates: the same task phrased differently resolves to the right ordinal; near misses
  -- same subject, different action -- come back null. Measured against the real model, counts
  recorded here.
- **Zero refs resolving to nothing.** An ordinal outside the shown set is rejected.
- Flag off: the verdict is recorded and **nothing is parked**. Flag on: it parks, the row says
  what it matched, the matched item is untouched.
- A proposed space that already exists is dropped; one failing the name rules is dropped.
  Accepting one creates it and files the item there; not accepting changes nothing.
- **The 22 classify fixtures, the 6 discriminating cases and slice 27's clarify eval all hold.**
  Slice 27's lesson, learned the hard way: a new instruction regressed a fixture that had always
  filed correctly, and only the fixtures caught it.
- Ask is unchanged: its tests pass untouched after `search` moves.
- Four sabotages, each turning a test red, then restored: trust an unresolved ref; park while the
  flag is off; accept a ref for an item never shown; accept a proposed space that already exists.
- `uv run pytest -q && uv run ruff check .`; `uv run pytest -m eval`; `npm run typecheck`,
  `npm run build`, `npm run ui`.

## Risk

**Parking a real capture is the bad failure.** It is why the flag ships off. Eight seeded cases
are not a false-positive rate on a real database, where titles sit far closer together than
anything a test invents.

**Two new fields on top of `clarify`.** The proposal object is getting busy, and slice 27 proved
that prompt weight has a cost paid somewhere you were not looking. Core filing is the guard, not
an afterthought.

**Moving `search` touches slice 26's work.** Ask's tests are the contract.

**Migration 0015 runs on the deployed database at the next deploy**, which has no backup. Additive
columns only, and that is not negotiable in this slice.

**Per-capture retrieval joins the hot path.** Cheap beside a ~10s model call, but it is measured
rather than assumed.

## What was built (2026-09-21, closed 2026-09-22)

Both parts, as planned. The one thing the plan did not foresee was in the *test*, not the code.

### The measurement that matters

**3/3 duplicates caught, 0/5 false positives**, every ordinal resolving to the right item and
none resolving to nothing:

```
'car insurance needs renewing before it lapses'  -> 901   (Renew the car insurance)
"i still need to go through Sarah's PRD"         -> 902   (Review Sarah's PRD)
'book the Istanbul flights'                      -> 904   (Book flights to Istanbul)
'schedule the car service'                       -> None
'email Sarah the PRD feedback'                   -> None
'buy new goggles for swimming'                   -> None
'renew my passport before the trip'              -> None
'pay the electricity bill'                       -> None
```

The near misses are the whole test. "Schedule the car service" against "Renew the car insurance"
and "email Sarah the PRD feedback" against "Review Sarah's PRD" are same-subject-different-action,
and both came back null. Matches what an earlier build measured, on a different model.

### The control that was not a control

The house-rule eval failed on `"prepare for the exam on Friday"`: `work` without the rule,
`None` with it. It reproduced on a second run, and a third measurement, in isolation, answered
the other way round (`None` without the rule, `work` with it).

**Corrected 2026-09-22.** This section originally said the reproduction "ruled out variance
between models" because it came after the model was pinned. It did not: the eval suite was still
building `CodexConfig(command="codex")` with no model, so both eval runs used the CLI's default
while only the isolated third run used `gpt-5.6-luna`. The flip-flop was therefore across two
models, not two runs of one. The conclusion -- that the capture sits on the fence and the control
was measuring its own wobble -- still holds, since a control that answers differently on two
models is no more usable than one that answers differently on two runs. But the evidence was
confounded and the sentence claimed more than it had.

So the capture is simply on the fence between `work` and `ideas`, and **the control was
measuring the wobble rather than the rule.** Worse, the assertion predated slice 27: it treated
any move to `None` as drift, when since slice 27 an ambiguous capture *correctly* comes back with
no space and a question. It was asserting that the classifier must not do the thing it was just
taught to do.

Two fixes, both to the test:

- The fence-sitter was replaced with `"book flights to Istanbul in March"`. The three controls
  now answer `finance, health, travel` identically with and without the rule.
- The assertion now names what leaking actually is: **a control landing in the space the rule is
  about**. A control that becomes `None` is the classifier declining to guess, which is honest
  and is not the rule reaching where it should not. Drift between two *definite* spaces still
  fails.

No prompt change was needed. The code was right and the test was wrong, which is worth recording
because the reflex after slice 27 was to reach for the prompt first.

## Verification -- what actually ran

Across two runs, because the subscription limit landed between them. **On the CLI's default
model, not the pin** -- the evals did not carry it until 2026-09-22, so these numbers describe a
different classifier than the app ships. They are kept as measured; re-running the suite now
measures the pinned model:

| | |
|---|---|
| duplicates | **3/3 caught, 0/5 false positives**, 0 refs resolving to nothing |
| house rule | **0/3 to 3/3** into `home`; controls `finance, health, travel` **identical** with and without |
| asking | three vague captures ask with real candidates; three placeable ones file silently |
| context, clarify, tell-it-why | all pass; the 1/6-to-6/6 figure itself is from the earlier default model, not re-printed on luna |

- `uv run pytest -q` -- **244 passed, 7 deselected**. `uv run ruff check .` clean.
- **Four sabotages each turn a test red**, then restored: trust an unresolved ref; park with the
  flag off; accept a proposed space that already exists; show the classifier real ids.
- `npm run typecheck`, `npm run build` clean; `npm run ui` **9/9**.
- Migration 0015 applied to the real local database (schema version 15, both columns present).
- On glass at 390px: *"Looks like #52 already here. Filing this keeps both."* linking to the
  matched item; the proposed space as a dashed `+ car` button at 46x44 that fills the sentence in.

**Settled 2026-09-22.** The suite was re-run in one go with the evals carrying the pin: **7
passed**, and this slice's numbers are unchanged on `gpt-5.6-luna` -- 3/3 duplicates named, 0/5
near misses. The figures above were measured on the CLI's default; these confirm them on the
classifier that ships.

## Still open

Nothing in the slice. `TARTIB_DUPLICATE_PARK` is off, by design: the verdict is being recorded
now so it can be judged on real captures before it is ever allowed to hold one back. Turning it
on is a decision for a later day, not a leftover task.
