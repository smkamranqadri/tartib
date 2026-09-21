# Slice 27: the AI contract

Planned 2026-09-21, after slice 26 closed. This is backlog entry 14, and slice 26 already took
its retrieval half out -- the classifier can see what exists now, and Ask carries a turn. What is
left is the contract itself: what you can say to the classifier, what it can say back, and what
it learns from you.

Three parts, one Phase, by the owner's decision. They are separable and the third is the clean
cut point if this runs long.

## Decided with the owner, 2026-09-21

- **All three in one slice.** Offered as a split -- the override and the question now, the
  examples once there was something to learn from -- and declined.
- **House rules, appended, not a whole-prompt replacement.** The shipped prompt keeps the JSON
  contract, the field definitions and the schema; the override is a block appended to it. One
  bad edit at 2am cannot stop every capture from filing, because the parts that make the output
  parseable are not reachable. Offered full replacement with a reset, and replacement validated
  by a live call before saving; both declined in favour of the safe one.
- **The redo path keeps overwriting the original proposal.** Raised because it destroys the exact
  signal part C wants -- telling the classifier why it was wrong erases what it first said --
  and the fix was one column. Declined. C therefore learns only from corrections made by editing,
  and this is a known, accepted narrowing rather than an oversight.
- **`clarify`, not `question`.** `shape: "question"` already means *you* asked Tartib something.
  This is the other direction and must not share the word.

## What earlier builds already settled

An earlier build of this same idea shipped all of part C and measured it. Recording the substance
here so this slice does not re-derive it:

- **Examples work when there is a correction to learn from.** Seeded steering went **0/4 to 4/4**.
- **Over-application is real, not theoretical.** On the first run the model moved an unrelated
  control -- an electricity bill -- from Home to Finance purely because unrelated corrections were
  in the prompt. The fix was one line: *an example informs only a capture of the same kind, and is
  ignored entirely when the subject resembles none of them.* Re-measured across six controls:
  **zero drift**. That line ships with part C from the start rather than after it bites.
- **Only a field the AI actually proposed may count as a correction.** That build's routing code
  filed a domainless task under a default, and counting that as a correction would have taught the
  model from the routing code rather than from the person. Pinned by tests there, and Tartib has
  the identical trap: `approve` does `fields.setdefault("shape", row["shape"])` and falls back to
  `fields["space"] = row["space"]`.
- **Padding is the fallback, never the default**, and only from items accepted untouched at high
  confidence. Those are the model's own uncorrected output; leaning on them teaches it its own
  habits back.
- **Up to 5 examples, corrections first**, scanned from the recent processed captures.
- **A seeded preference proves nothing if the model would pick it unaided.** That build's first
  live test seeded "bills go under Home", which both runners already did, so it discriminated
  nothing. Slice 26 hit the identical trap and the fixtures had to be rebuilt.
- **Sabotage the rules and watch a test go red.** Three worth keeping: count the approve path's
  fallback as a correction; put padded examples before real ones; pad with low-confidence items.
  Each should turn a test red, and if it does not, that test is decorative.
- From a different build, one idea for part B's shape: a waiting item is defined by **the single
  action that unblocks it**. That is what a clarify block should feel like -- not a form, one
  question with the answers as buttons.

Neither earlier build has an editable prompt or a classifier that asks a question. Parts A and B
are new ground with nothing to copy.

## The thing this slice cannot prove

**Part C will almost certainly ship inert, and that is measured, not feared.** The earlier build
deployed it and found **one detectable correction in its whole history, zero on tasks**; its live
readout was 5 examples sent, 0 of them corrections -- all padding. Checked again directly in that
build's database while planning this: 22 captures became live tasks, **zero** corrections across
title, domain or project. Tartib's own database says the same thing today: **49 items carry a
proposal and not one differs from what was filed**, and there are zero redo reasons.

So part C is machinery that is correct, cheap, and has nothing to eat. It starts paying the day
the owner begins overriding the classifier, and not before. Two consequences, both of which
belong in the code rather than in someone's memory:

- The readout must say how many of the examples sent were **real corrections**, so `0` reads as a
  fact about the data rather than a bug in the feature.
- Nobody should expect part C to move filing quality in this slice's eval. If it appears to,
  suspect the fixture before believing it.

## Steps

**A. House rules.**

1. `app_state` gains `classifier_house_rules` -- no migration, that table already holds the digest
   date and the login counters. Read and write through `store`.
2. `classify.PROMPT` gains a delimited block for it, empty by default and **byte-identical to
   today's prompt when unset**. Budgeted like slice 26's context block.
3. `GET`/`PUT` on a settings route; `config.py` reports whether any are set.
4. Settings' existing Classifier card gains the editor, beside the auto-file threshold, with
   clear-to-default. Character cap shown.
5. Classify only. Ask answers questions, it does not file, and the two prompts share their rules
   through `store.item_header` already.

**B. The classifier may ask you something.**

6. `Proposal` and `_PROPOSAL_SCHEMA` gain an optional `clarify`: a question, 2 to 6 options with
   a short label and an optional detail line, single or multiple choice. It rides inside
   `proposal_json`, which already stores the whole proposal, so no new column and no migration.
7. The prompt earns it: offer a clarify block instead of guessing when the space is genuinely
   ambiguous, never when confident.
8. `ApprovalCard` renders it above the sentence -- the question, then the options as buttons, one
   tap to apply and file. Old rows have no clarify block and must render exactly as they do now.
9. `approve` accepts a chosen option and applies it.

**C. Corrections as examples.**

10. `store.corrections(conn, limit)`: recent filed items whose stored proposal differs from what
    they became. Conservative by the rules above -- only fields the AI actually proposed, and the
    approve path's own fallbacks never count.
11. Up to 5, corrections first, padded with accepted high-confidence items only when short.
12. The prompt block, carrying the over-application guard line from the start.
13. A readout of how many were real corrections.

## Verification

- With no house rules set, the built prompt is **byte-identical** to today's. Asserted, not eyeballed.
- A house rule the model cannot guess changes filing, measured with and without it.
- A deliberately hostile house rule still parses and still files.
- A low-confidence capture returns a clarify block; it renders at 390px with 44px targets; one tap
  files it correctly. Checked in the committed UI suite, not described.
- A confident capture gets no clarify block and the sentence is unchanged.
- A real correction is detected; the approve path's `shape` and `space` fallbacks are **not**
  counted -- a test that fails if they are.
- Padding only when corrections are short, and only from high-confidence accepted items.
- Over-application: six unrelated controls, zero drift with examples present.
- The three sabotages above each turn a test red, then are restored.
- Existing evals hold: 22 classify fixtures, the 6 discriminating cases, 3 tell-it-why.
- `uv run pytest -q && uv run ruff check .`; `npm run typecheck && npm run build`; `npm run ui`.

## Risk

**Three parts in one Phase.** C is the cut point and nothing in A or B depends on it.

**B changes the proposal schema**, which every filing path reads. Rows written before this slice
have no clarify block; they must stay readable, and that is a test, not an assumption.

**A is the part most likely to be used wrongly**, which is why it cannot reach the contract. The
residual risk is a house rule that is merely bad advice rather than malformed -- that shows up as
worse filing, and the only defence is that it is one field you can clear.

**C's eval can lie to you.** A seeded preference the model would pick anyway proves nothing, and
this has now caught two slices running.
