# Slice 29: what the AI costs

Planned 2026-09-22, after slice 28 closed. The backlog's "AI usage on record", promoted when the
thing that blocked it stopped being unknown.

Tartib runs a subprocess for every capture and has never known anything about it: not how long it
took, not how much it consumed, not how often it failed, and not that the subscription limit has
now stopped work four times in two days. The app's one expensive operation is the one it keeps no
record of.

## What is no longer unestablished

The backlog said *"whether the Codex CLI reports token counts at all is unestablished and decides
how much of this is possible."* Established 2026-09-21:

- `codex exec --json` prints the turn as JSONL on stdout: `thread.started`, `turn.started`,
  `item.*`, then `turn.completed` or `turn.failed`, and `error` carrying a message.
- **`turn.completed` carries a `usage` object** with `input_tokens`, `cached_input_tokens`,
  `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens` and `total_tokens`.
- `--json` does not replace `--output-last-message`; the reply still goes to the file.
- Two traps, both hit while establishing it: the CLI blocks forever reading a non-tty stdin
  unless it is closed, and the `codex` on PATH here is a wrapper, not the binary.

And the pinned model has a real public price: `gpt-5.6-luna` at **$0.20/M input, $1.20/M output,
$0.02/M cache read, $0.25/M cache write**, with a higher tier only above 272k of context.

## Decided with the owner, 2026-09-22

- **Fetch prices, but keep only the model's numbers.** The catalogue is 5.17MB to read four
  figures. Refresh at most daily, write ~100 bytes, ship the same numbers as a default in code so
  a first run and a failed fetch both still cost correctly. Offered shipping them in code with no
  network at all, and putting them in env beside the pin; both declined.
- **A row per call, kept.** Offered rolling up after 90 days and running totals with no table.
  Rows answer "what did slice 26's context add"; roll-ups cannot be turned back into rows.
- **Settings, plus the cost on the item.** A per-item figure is what makes it concrete.
- **The usage limit is its own kind of failure**, recorded with the reset time it reports, and
  surfaced. The quota is the scarce resource here; the money is not.

## Two things that will bite if they are missed

**`--json` would wreck the error messages, which are the most valuable text in this system.**
`_run` builds `CodexError` from the last line of stderr-or-stdout. With `--json`, stdout is JSONL,
so that last line becomes a JSON blob. *"You've hit your usage limit ... try again at 11:46 AM"*
is exactly what made four quota stalls diagnosable, and it arrives as an `error` event's
`message`. The parser must take it from there, keeping the old path as a fallback. **This is a
regression risk on the thing that has saved the most time this week**, and it is an acceptance
check rather than a note.

**The cost may be double-counted, and it cannot be checked until the quota returns.**
`output_tokens` and `reasoning_output_tokens` are both reported, and reasoning tokens are
normally *included in* output. Added naively, the cost roughly doubles on a reasoning model --
which luna at medium effort is. One real call settles it: reconcile `total_tokens` against the
sum of the parts. **No cost figure is shown until that arithmetic is confirmed.**

## Also true, and worth stating rather than discovering

- **A timeout records zero tokens and still costs quota.** The 120s kill yields no
  `turn.completed`, so calls and tokens will legitimately disagree, and the readout must not
  imply every call has tokens.
- **The cost is an estimate twice over**: the subscription reports no cost, and the catalogue is
  list price. Rule 9 governs the copy -- it must not read as a bill.
- **Base tier only.** Tartib's prompts are around 4k against a 272k boundary.

## Steps

1. **`codex.py` reports.** Add `--json`. Parse the event stream: `usage` off `turn.completed`,
   and the message off `error` / `turn.failed`. `run_json` returns a small `Reply` (data plus
   usage) rather than a bare dict; the three call sites -- classify, ask's answer, ask's term
   expansion -- update.
2. **Migration 0016, `ai_calls`.** kind (`classify` / `ask` / `terms`), model, the six counts,
   `duration_ms`, `ok`, a failure reason, the reported reset time when that reason is the usage
   limit, and a nullable `capture_id` so per-item is a join rather than a guess. New table,
   nothing altered.
3. **`store.record_call`**, and the totals the readout needs. **Recording never breaks a
   capture**: a failed write is swallowed, because a bookkeeping error must not cost a note.
4. **`usage.py`**: the pinned rates as a shipped default, the cost calculation, and a refresh at
   most once a day that writes only this model's numbers. Failed fetch keeps the last good copy.
5. **The readout.** Settings: calls, tokens, estimated cost, a per-capture average, and when the
   quota last bit and how often. The item page's Proposal accordion: what that capture cost.
   Both say plainly that it is an estimate and that the subscription reports no cost at all.
6. **`fake_codex.py` emits events**, including a usage-limit error, or none of this is tested.

## Verification

- **`total_tokens` reconciled against the sum of its parts on a real call**, and the formula
  counts reasoning tokens exactly once. Recorded here. Nothing is displayed before this passes.
- A successful call records one row with six counts and a duration.
- A failed call records `ok=false` with the CLI's message intact -- specifically the usage-limit
  text with its reset time captured.
- A timeout records a duration and no tokens, and the readout survives it.
- **Error messages are no worse than today** with `--json` on. The same text reaches `CodexError`.
- A capture's cost is reachable from its item; an ask's call stores a null capture.
- Prices: no network and no cache falls back to the shipped default; a good fetch writes only the
  model's rates; a failed fetch keeps the last good copy.
- Recording failing does not fail the capture.
- The existing **244 tests and 7 evals hold** -- the transport is shared by everything.
- `uv run pytest -q && uv run ruff check .`; `uv run pytest -m eval`; `npm run typecheck`,
  `npm run build`, `npm run ui`.

## Risk

**The transport is shared by every AI call in the app**, Ask included. That is the blast radius,
and it is why the error-message check is an acceptance criterion rather than a hope.

**The double-count question is unsettled**, and the whole cost figure rests on it. Build against
the fake; hold the number until one real call confirms the arithmetic.

**Assumes `turn.completed` always carries usage on success.** If it sometimes does not, the row
records zero and says so rather than guessing.

**Migration 0016 runs on the unbacked-up deployed database.** A new table, nothing altered.

**Outbound network is new surface on the VPS.** Once a day, one host, and the app works with it
blocked -- which the acceptance checks require.

## What was built (2026-09-22) -- built, two things unproven

Steps 1 to 6, all of it. **The slice is not closed**, and for a sharper reason than the plan
anticipated: see Still open.

### The regression the plan predicted, caught by an existing test

Adding `--json` broke `test_bad_cli_falls_back_to_one_note` on the first run, exactly as written:
stdout became JSONL, so the last line -- which is where `CodexError` got its message -- became a
JSON blob. `parse_events` now takes the message from the `error` event, with the old
stderr-or-stdout path kept as a fallback for anything that never reaches the stream. The test
went green again without being touched, which is the proof that the message is no worse than
before.

### Reasoning tokens, and why the cost is still hidden

`Usage.billable()` returns fresh input, cached input, cache writes and output -- and
**deliberately not reasoning tokens**, on the reading that the CLI already counts them inside
`output_tokens`. Pricing both would bill reasoning twice, and on a reasoning model at medium
effort that is most of the bill. *That reading is not yet confirmed.* `/api/usage` computes a
cost and returns it with `cost_verified: false`; the UI shows tokens, calls and time, and says in
as many words that a cost estimate is not shown yet because the arithmetic has not been checked.
The committed UI suite asserts that no currency symbol appears while `cost_verified` is false.

An attempt to settle it without the quota failed: the earlier build's 324 stored AI jobs record
no token counts at all, so there was nothing to reconcile against.

### The rest

- **Migration 0016, `ai_calls`**, one row per call: kind, model, the six counts, duration, ok,
  the CLI's own failure text, a reason, the reported reset time, and a nullable `capture_id`.
  Not a foreign key on purpose -- deleting a capture must not erase the record that the work was
  paid for.
- **`store.record_call` never raises.** A bookkeeping failure must not cost a capture, and there
  is a test that calls it against a database with no table at all.
- **The usage limit is its own failure**, with the reset time parsed out of the CLI's message.
  Four stalls in two days and the app knew nothing about any of them; now it does.
- **`usage.py`** holds the pinned rates as a shipped default and refreshes at most daily,
  writing only this model's four numbers -- the catalogue is 5.17MB to read four figures. Cached
  beats shipped; a corrupt cache falls back rather than failing; an unknown model costs nothing
  rather than guessing.
- **Usage reaches the recorder through an `on_usage` callback** rather than a changed return
  type, so the six eval call sites that do not care were left alone.

## Verification -- what actually ran

- `uv run pytest -q` -- **264 passed, 7 deselected** (was 244; +20, in a new `test_usage.py`).
- `uv run ruff check .` clean; `npm run typecheck` and `npm run build` clean.
- `npm run ui` -- **10/10**, including a new check that the readout renders and that **no money
  appears while the arithmetic is unverified**.
- Migration 0016 applied to the real local database (schema version 16).
- On glass at 390px, empty and populated:

```
3 calls · 11,350 tokens · 21s of waiting
About 5,675 tokens per capture, across 2.
1 failed. 1 of them hit the subscription limit, last reporting a reset at 11:46 AM.
Model gpt-5.6-luna. A cost estimate is not shown yet — the arithmetic has not been
checked against a real call.
```

### Added mid-slice: the quota readout (2026-09-22)

Asked why the subscription limit kept landing, since the pinned model normally lasts. Measured
rather than guessed, and the answer was arithmetic:

- **One `pytest -m eval` run is 64 model calls**, fired concurrently -- 22 classify fixtures,
  12 for context (6 blind + 6 seeing), 12 for the house rule, 8 duplicates, 6 asking, 3
  tell-it-why, 1 hostile rule.
- **Each call got 2.5x bigger.** Slices 26 to 28 took the classify prompt from 3,915 to 9,741
  characters against a full database -- roughly 978 to 2,435 tokens. So one eval run is about
  155k input tokens before output and reasoning, and the suite ran six times in a day.
- The quota is per-account, so this competes with the owner's own Codex work, and there are
  **two rolling windows**, which is why reset times jumped around the clock.

Then the useful part: the CLI already reports this. A **`token_count`** event carries
`rate_limits` with `primary` and `secondary` windows, each with `used_percent`, `window_minutes`
and `resets_at` -- and slice 29 was already parsing that stream and throwing the event away.

So it is parsed now. The latest reading goes to `app_state` (a point in time, not a history --
what matters is how full the window is *now*), rides on `CodexError`, `ClassifyError` and
`AskError` so a call that failed *because* the window is gone still reports its level, and shows
in Settings as the **fullest of the two windows**, since that is the one about to stop you. It
turns red at 80%.

The shape was read off the binary, not a live event, so it is parsed defensively: anything
missing or odd stays `None` rather than becoming a confident `0`, which would read as "plenty
left". A test pins that.

```
Quota 92% used of the 5 hour window, resets 11:46 AM.
```

## Still open -- and one of these is deploy-blocking

Both need the same quota window (**11:46**), and they should be done in this order:

1. **Confirm `--json` does not break a real successful call.** This is the serious one. `--json`
   is on for *every* AI call in the app now, and it has only been exercised against the fake. The
   one real attempt made while establishing the event format failed on quota before the turn
   completed, so **it has never been confirmed that the reply file is still written when the
   stream is on**. If it is not, every capture fails. Nothing deploys until one real capture
   classifies end to end.
2. **Reconcile the token arithmetic.** Compare `total_tokens` against the sum of the parts on a
   real call and confirm reasoning tokens sit inside `output_tokens`. Then flip
   `cost_verified` and show the figure.
3. **Confirm the `token_count` shape** against a real event. The field names came from the
   binary; the parser tolerates them being wrong, but nobody has seen one.

Until (1) passes, this slice is a liability rather than a feature, and `v1.1` must not carry it.
