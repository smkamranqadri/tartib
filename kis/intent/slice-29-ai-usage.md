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
