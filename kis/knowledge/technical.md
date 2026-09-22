# Technical

How Tartib is built. Proven by the Phase 1 to 4 scaffold on 2026-09-17.

## Layout

```text
backend/tartib/     FastAPI app. config, db, deps, auth, captures, items, spaces, queries, ask, briefs, classify, codex, runner, reminders, sessions, push, vapid, store, clock, reclassify, main
backend/tartib/migrations/   numbered .sql, applied at startup, tracked in schema_version
backend/tests/      pytest + TestClient; the AI runs as a real subprocess pointed at fake_codex.py
frontend/src/       React + Vite + TS. App.tsx, Capture.tsx, api.ts, push.ts, types.ts, format.ts, useLoad.ts, screens/ (Home, Inbox, Recent, Spaces, Space, Settings, ItemPage, Login; Space renders `screens/layouts/Panes.tsx`, which shares `layouts/shared.tsx`), components/ (one per pattern, listed under Frontend shell)
frontend/public/fonts/  JetBrains Mono 400 and 600, self-hosted and precached by the worker
frontend/tools/     themes.py, which generates the palette block in styles.css and enforces the contrast floors
frontend/public/    manifest.webmanifest, sw.js (app shell + push; hand-bumped SW_VERSION), icons 180/192/512
Dockerfile          multi-stage: node builds dist; python:3.12-slim + node runtime + @openai/codex runs uvicorn
docker-compose.yml  one service, volume tartib-data at /data, ~/.codex mounted at /root/.codex, mem_limit 512m
```

## Serving

One container. Uvicorn, one worker, started with `--factory tartib.main:create_app`.
FastAPI serves `/api/*`; anything else returns a file from the static dir if it exists, otherwise `index.html` (SPA fallback). Unknown `/api/*` paths 404.
In dev, Vite proxies `/api` to port 8000.

## Storage

SQLite, WAL, stdlib `sqlite3`, one connection per request opened in a threadpool. No ORM.
`captures(id, raw_text, source, created_at, status, error, answer_json, classified_at, client_id)` is the stored input, one row per capture. `client_id` (migration 0009) is minted by the browser before its first send, so a capture queued offline and sent twice is recognised rather than duplicated: `POST /api/capture` looks it up and answers 200 with the existing id instead of 201 with a new one, and the unique index settles the race when two sends both find nothing. It is nullable and unique only among rows that have one -- SQLite allows repeated NULLs in a unique index -- because every capture from curl, the Shortcut, or before 0009 has none. A repeat is never re-enqueued; the first attempt did that, and startup re-queues anything still pending.
`items` are classifier output: `capture_id`, own `raw_text` excerpt, nullable `space`, task fields, `stage` (attention | filed), `proposal_json`, `proposal_error`, `classified_at`. A CHECK forbids `filed` with a null space. `updated_at` (migration 0003) is internal, set by AFTER INSERT / AFTER UPDATE triggers with millisecond UTC timestamps (since slice 30 `store.insert_item` writes it itself, from the same millisecond timestamp as `classified_at`, so an item nobody has touched is exactly `updated_at = classified_at`; it must stay in milliseconds, because `updated_at` is compared as a string and `…:00Z` sorts after `…:00.100Z` from the same second); the update trigger fires only when the statement neither set `updated_at` itself (so it never recurses) nor changed `reminded_at` (narrowed by 0005, below).
`briefs(space PK, fingerprint, text, item_ids JSON, created_at)` caches one AI brief per space. Fingerprint = item count, newest item id, and today's session count for the space, so adding or removing an item or finishing a session in it regenerates the brief; the refresh icon forces it. The prompt gains a line with that count when it is not zero. Fingerprints are only checked when a brief is opened, so a session costs a Codex call only the next time that brief is looked at.
`spaces(name PK, position, created_at)` (migration 0004) is the list of spaces; `spaces.seed_spaces` fills it from `TARTIB_SPACES` once when empty; `store.list_spaces(conn)` is what the classifier, validation, summary, and reconcile read. Migration 0004 also dropped the item text immutability trigger and made the FTS update trigger fire on `raw_text` too.
At startup, after migrations, `store.reconcile_spaces` moves items whose space is no longer in the `spaces` table to attention with no space. Migration 0002 (2026-09-17) created captures, backfilled one per item, rebuilt items, mapped `space='inbox'` to null + attention, dropped stage=inbox placeholders (their captures stay pending).
`subscriptions(id, endpoint UNIQUE, p256dh, auth, created_at, last_seen_at, failures)` (the last column from 0006) and `app_state(key PK, value)` arrived with migration 0005, which also added `items.reminded_at` (UTC ISO, null = not sent) and wrote off every reminder already due, so the first tick after that deploy is silent. 0005 also narrowed `items_touch_update` to skip writes that change `reminded_at`: a fired reminder is not a human touch and must not reset the stale clock. The one write that clears `reminded_at` (`store.update_fields`, when `remind_at` actually changes) sets `updated_at` itself.
**Links are an index of the text** (slice 33): `[[Title]]` names an item by its first line, keyed by `store.link_title` (`title_of`, a link inside the line read as its words) case-folded; `[[space:name]]` names a space (`space_of`; the prefix wins over any item title). Migration 0020's `item_keys` and `item_links` are written by `store.index_links` from `insert_item` and `update_fields` -- every text write goes through one of the two -- cascade on delete, and are rebuilt whole at startup (`reindex_links`); they sit apart from `items` so the touch trigger never fires for bookkeeping. `store.LINK` is the server's grammar and skips fences and code spans; the client lexes `[[…]]` as its own token in a dedicated `Marked` instance in `markdown.ts`, because `marked.lexer(text, options)` ignores what `marked.use` registered. The two disagree on a few rare shapes (a lone fence mid-line, a code span across a line break, `\[[X]]`, indented code). A first-line change rewrites `[[Old]]` in the items that link to it through `update_fields` (so their `updated_at` moves and an open editor gets the stale-save question), reading each text at the moment it is rewritten, at most three levels of nested retitling deep, and not while another item still has the old key or when `[[New]]` would not key back to the item; a space rename does the same for `[[space:old]]` (`rewrite_space_links`). `GET /api/items/{id}` carries `links`, `space_links` (each as written, to its target or null) and `linked_from`; `/api/links/suggest`, `/api/links/resolve` and `/api/spaces/{name}/linked` are in `links.py`.

**Pick for me marks its own stars** (slice 32): `items.picked_at` (migration 0019) is set only by `POST /api/pick`, and `store.update_fields` clears it whenever `starred` is written, so any star a person sets or clears is theirs. A pick unstars every row with `picked_at` set and stars the new ones in one transaction, after the reply is validated; candidates are open filed tasks not on Today as it would be without pick stars (`queries.today_rows(without_picks=True)`, the one definition of Today), labelled `t1`, `t2`, ... so an invented label resolves to nothing. Its reason is appended as a `Picked for today:` thought. A pick's star moves `updated_at` like any star, so a picked task leaves the stale list. Its `ai_calls` kind is `pick`, with `candidates_n` counted.

`ai_calls(id, created_at, kind, model, capture_id, ok, failure, reason, resets_at, duration_ms, + six token counts, + prompt_chars, candidates_n, examples_n, corrections_n, house_rules)` (migrations 0016 and 0017) is one row per AI call. The second group is **what was in the prompt**, written at the moment of the call because none of it can be worked out afterwards -- the prompt is not kept and the database it was built from moves. It exists because the prompt's *parts* are capped (space context 4000 chars, house rules 2000) while the whole is not: examples are capped at five entries and candidates at eight items, neither by length, so the prompt can grow with the database and nothing would otherwise say so. `capture_id` is null for an Ask and is **not** a foreign key on purpose: deleting a capture must not erase the record that the work was paid for. Rows rather than counters, because rows can answer what a prompt change cost and a counter cannot.
`items_fts` is an FTS5 external-content table over `raw_text` and `title`, synced by triggers.
**`title` is derived** (slice 31): `store.title_of` flattens the first non-empty line, and every write path sets it -- `insert_item` adds the AI title above the text first (`retitle`), and `update_fields` re-derives it on any text, title or shape change. A `title` edit is an edit of line one (`retitle(replace=True)`); moving a note to a task adds the title above. Comparisons go through `same_title`, which ignores case and markdown, so "Buy milk" over "buy milk" is never added. Redo keeps its hands off line one once it is no longer the title the classifier last proposed (`proposal_json.title`). Migration 0018 did the same to existing tasks in SQL, with the touch trigger dropped for the rewrite so `updated_at` did not move; its first-line test is an approximation (case and a leading `#*>-` only), which is why the Python path is the one that writes from then on.
A BEFORE UPDATE trigger aborts any write to a capture's `raw_text`; the matching trigger on items was dropped in migration 0004, so a filed item's text is editable.
All timestamps stored as UTC ISO 8601 with `Z`; `due` is `YYYY-MM-DD`.

## Auth

`POST /api/login` compares in constant time, sets an HTTP-only SameSite=Lax cookie signed with `itsdangerous`, 30 days.
`secure` flag only when the request scheme is https. Every `/api/*` route except login and health accepts that cookie or `Authorization: Bearer <TARTIB_PASSWORD>`.
`TARTIB_SECRET` is optional; when unset it is derived from the password, so changing the password logs everyone out.
`auth.check_password` is the one place a password is compared, and the backoff lives there rather than on the login route: every `/api` route also takes the password as a bearer token, so watching `/api/login` alone would just move guessing to `/api/today`. The count is global, not per-IP -- behind a proxy the address only arrives in a header, and one password is one account. Four failures are free; from the fifth each attempt answers 429 with `Retry-After`, in a window doubling from 30s and capped at 5 minutes, and a success clears it. Counters live in `app_state` (`login_failures`, `login_blocked_until`), so a crash loop is not a free reset. While blocked the password is not even compared: doing so would be an oracle saying which guess was right, and the price is that your own login waits too. `require_auth` tries the cookie first so a signed-in browser never consults the counter and cannot be locked out by someone else's guessing.
The image runs uvicorn with `--proxy-headers --forwarded-allow-ips "*"`. `--proxy-headers` alone trusts `X-Forwarded-Proto` only from `127.0.0.1`, and behind a reverse proxy the peer is the container network, so the app saw `http` and set the session cookie without `Secure` on an HTTPS site. `"*"` is safe in this shape only: nothing reaches the port except the proxy.

## Classification runtime

`codex.py` is the one AI transport: `run_json(prompt, schema, cfg)` runs the Codex CLI and raises `CodexError` on any failure; there is no fallback. Since slice 29 it returns a `Reply` (the parsed data plus a `Usage`), not a bare dict. Codex runs `codex exec --ephemeral --skip-git-repo-check --ignore-user-config --sandbox read-only --json --output-schema <tmp> --output-last-message <tmp> [--model M] [-c model_reasoning_effort=E] <prompt>` with stdin closed (Codex blocks reading stdin otherwise), in a temp working dir so no AGENTS.md leaks in. Timeout kills the process.
**The error message comes off the event stream, not off stdout's last line (slice 29).** `parse_events` reads `usage` from `turn.completed` and the failure text from `error` / `turn.failed`; the old stderr-or-stdout path survives as a fallback for anything that never reaches the stream. This matters because `--json` turns stdout into JSONL: taking the last line, as `_run` used to, yields a JSON blob instead of "You've hit your usage limit ... try again at 11:46 AM", which is the text that makes a stalled run diagnosable. An existing test caught it the moment `--json` went on.
**The CLI reports no total, and no reasoning (slice 29, measured).** A real `turn.completed` carries five counts -- `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens` -- and **no `total_tokens` at all**, so it is computed as input + output when absent or every row stores a zero. `reasoning_output_tokens` came back 0 on every real call, so the double-count question does not arise in exec mode. The cost reconciles exactly: 15,579 input and 145 output at $0.20/M and $1.20/M give 0.0032898.
**A capture costs 13,000 to 15,600 input tokens, and only ~1,900 to ~2,400 of that is Tartib's prompt** (two measurements, 2026-09-22). The other ~13,100 is the CLI's own instructions, sent on every call. This dwarfs anything the app's own prompt does, and it is why an eval run is ~810k input tokens rather than the ~155k the prompt sizes suggest.
**`codex exec` emits no `token_count` event**, so the quota windows are parsed, stored and displayed but stay empty in practice. The readout is built and dormant; its absence is the CLI not telling us, not the app failing to ask.
**Reasoning tokens are already inside `output_tokens`.** `Usage.billable()` returns fresh input (input minus the cached part), cached input, cache writes and output, and **not** reasoning -- pricing both would bill reasoning twice, which on a reasoning model at medium effort is most of the bill. *This reading is not yet confirmed against a real call*, which is why `/api/usage` carries `cost_verified: false` and no money is displayed.
**`store.record_call` never raises.** A bookkeeping failure must not cost a capture; a test calls it against a database with no table at all. The usage limit is its own `reason` with the reset time parsed out of the CLI's own words, because the quota is the scarce resource here -- a subscription reports no money cost at all.
**Prices work with the network blocked (`usage.py`).** The pinned model's four rates ship in code; a refresh runs at most once a day and writes only that model's numbers to `ai-prices.json` beside the database (created on the first successful refresh, so its absence is normal) -- the catalogue is 5.17MB to read four figures. Cached beats shipped, a corrupt cache falls back rather than failing, a failed fetch keeps the last good copy, and an unknown model costs nothing rather than guessing.
**The model is pinned, and the user's own Codex config is deliberately ignored.** `--ignore-user-config` means `~/.codex/config.toml` is never read, so a setting on a workstation cannot change how captures are filed -- which also means reasoning effort must be an explicit `-c model_reasoning_effort=` override rather than a config key. Unset, the CLI resolves its own default at runtime (there is a models manager in the binary, not a constant), and that default can move underneath a deployed app with nothing to say it did: the classifier would appear to get better or worse on its own. Pinned 2026-09-21 to **`gpt-5.6-luna`, reasoning `medium`**, via `TARTIB_AI_MODEL` and `TARTIB_AI_REASONING`. Both are environment, so **the deployed app needs them in its CapRover config** or it silently keeps using the CLI default.
**What the classifier is shown about what exists (slice 26).** `store.classify_context(conn)` returns one `SpaceContext` per configured space -- counts of open tasks and notes, plus the `CONTEXT_PER_SPACE` (5) most recent **filed** items. Filed only: an item sitting in attention is a guess nobody confirmed, and showing guesses as examples teaches the classifier its own mistakes. `classify.render_existing` renders it and trims to `CONTEXT_BUDGET` (4000 chars) by dropping the oldest example from the fullest space until it fits, so counts survive and examples are what is expendable; a 400-item database renders at ~3.7k. It is built server-side in one place because both callers need the same thing: `runner._load` for a capture and `items.py` for a redo. `Context.existing` defaults to empty, so a caller with no database still builds one.
`store.item_header(row)` is the single owner of what one item looks like to the AI, used by both prompts. `store.context_line` wraps it for classify and adds `CONTEXT_EXCERPT` (60) characters of a **note's** first line, because a note's header is space, shape and date and carries no content at all -- ask gets away with it only because the item's text follows underneath.
**House rules (slice 27).** `app_state.classifier_house_rules`, owned by `store.house_rules` / `set_house_rules`, capped at `HOUSE_RULES_MAX` (2000) and edited in Settings' Classifier card. They are **appended** to the shipped prompt, never substituted into it: the JSON contract, the field definitions and the schema stay in code where no saved edit can reach them, so a bad rule gives bad advice rather than stopping every capture. The block is absent entirely when unset, and the prompt is then byte-identical to the shipped one -- asserted, not assumed. Measured: a rule moved three car captures 0/3 to 3/3 into `home` with zero drift on three unrelated controls, and a rule telling the model to ignore everything and reply with one word still parsed and still filed.
**What the Codex CLI tells you about a call** (slice 29). `codex exec --json` prints the turn as JSONL events on stdout: `thread.started`, `turn.started`, `item.*`, then `turn.completed` or `turn.failed`, and `error` with the message. **`turn.completed` carries a `usage` object** with `input_tokens`, `cached_input_tokens`, `cache_write_input_tokens`, `output_tokens`, `reasoning_output_tokens` and `total_tokens` -- so token counts per call are available, which the backlog had listed as unestablished. `--json` does not replace `--output-last-message`; the reply still goes to the file. Two traps, both hit while establishing this: the CLI **blocks forever reading a non-tty stdin** unless stdin is closed (which is why `codex.py` passes `DEVNULL`), and the `codex` on PATH here is a wrapper script -- the real binary is under the npm package, which is where the event names can be read off.
**Pointing at an item: ordinals, never ids (slice 28).** `store.similar_items(conn, text)` returns the filed items that resemble one capture, each paired with an ordinal `i1`, `i2`, ...; the map back to real ids **never leaves the server**, and `store.resolve_ref` turns the model's answer into an id or into None. That is the whole defence and it needs no validation rule: an ordinal the model invents resolves to nothing, whereas an invented id can be a real item it was never shown, and a schema check cannot tell the difference because a made-up integer is a valid integer. `store.item_header(row, ref)` therefore takes the label to print -- Ask passes the real id, because it validates cited ids against the set it retrieved; classify passes the ordinal; the space context passes None and prints no label at all. Retrieval (`retrieval_query`, `search`) lives in `store.py` rather than `ask.py` so classify can use it without importing Ask. Measured on the pinned model: 3/3 duplicates named, 0/5 near misses, 0 refs resolving to nothing.
**Why an item waits (slices 28 and 30).** `items.wait_reason` is a short code -- `no_space`, `low_confidence`, `duplicate`, `asked`, `split`, `whole` -- not display text, because the client already has the matched item and writes the sentence itself. `items.duplicate_of` is recorded **whether or not parking is on**: `TARTIB_DUPLICATE_PARK` (default off) decides only whether a suspected duplicate is held back, so the verdict can be judged against real captures first. Nothing is ever merged; the matched item is untouched.
**A split waits, and can be put back (slice 30).** `Runner._apply` counts the non-question proposals; more than one means none files, whatever the confidence or policy, and each carries `split`, which `wait_reason_for` checks before every other reason. `store.keep_whole(conn, capture_id)` inserts one waiting note from the capture's `raw_text` (reason `whole`: the pieces' space when they agree, otherwise a `clarify` between their spaces) and deletes the pieces, only while `_untouched_split` holds: every item of the capture still waiting as `split`, `updated_at = classified_at`, no thoughts, no feedback, no session. A deleted piece does not block it. `store.split_info` adds `split: {of, whole}` to `/api/attention` items so the card needs no extra request. `reclassify` inherits all of it through `_apply`.
**A proposed space does nothing until it is accepted (slice 28).** `new_space` is a proposal: `_clean_new_space` drops it if it already exists or fails the name rules the Spaces page enforces, and an item carrying one waits exactly as an unknown space makes it wait. Accepting is what creates it, by either route -- approving as-is, or choosing it in the sentence, where the name still does not exist at the moment the client sends it. `spaces.add_space` is the one creator, shared with the Spaces endpoint.
**Asking must be balanced against deciding (slice 27, measured).** The prompt carries two instructions that pull against each other on purpose: a null space should become a question, *and* asking is not a way to avoid choosing -- if any space is a reasonable fit, name it. The first alone was measured and regressed filing: a fixture that had always filed under work came back with a null space and a question offering [work, finance], because nulling had become the comfortable option. Neither line works without the other, so neither should be edited alone.
**The clarify block (slice 27).** A proposal may carry `clarify`: one `field` (`space` or `shape`), a question and 2 to 6 options of `{value, label, detail}`. It rides inside `proposal_json`, so no migration and old rows simply have no key. `_clean_clarify` drops any option whose value is not a configured space (or not task/note) and drops the whole block below two surviving options -- rule 7 in button form, because a button that cannot file is worse than a null field. **A proposal carrying one never auto-files**, whatever its confidence or the space's policy, in both the runner and the redo path. Multiple choice was in the backlog and has no meaning here: a field holds one value and there is nothing like tags for a multi-answer to land in.
**Examples (slice 27).** `store.classifier_examples` returns up to `EXAMPLES_MAX` (5) from the `EXAMPLES_SCAN` (120) most recent filed items, corrections first, padded with items accepted untouched at or above the auto-file threshold only when short. **Only a field the classifier itself proposed may count as a correction**: when it proposed no space, `approve` supplies the item's own, and counting that would teach the classifier from the filing code instead of from the person. The prompt block carries the over-application guard -- an example informs only a capture of the same kind and is ignored entirely when the subject resembles none -- because an earlier build watched an unrelated bill move spaces purely because unrelated corrections were present. `/api/config.corrections` reports how many are real; it is 0 today and that is the state of the data, not a fault.
`classify.py` builds the filing prompt (user-authored, verbatim, plus a `text` excerpt bullet), validates `{"proposals": [...]}`, and normalizes: questions carry nothing, unknown spaces become null and cap confidence at 0.6, notes drop task fields, naive reminder times are converted from `TARTIB_TZ` to UTC.
`runner.py` queues capture ids. Per capture: classify, insert one item per non-question proposal (excerpt as raw_text, filed or attention by space + threshold), answer the first question proposal via `ask.answer_question` and store it on the capture, mark done. Any failure: one null-space note in attention, capture status error.
`SearchAsk` no longer answers where it stands (slice 21): it dispatches `tartib:ask` with the question and the space, `AskBar` fills itself in and answers there, so an answer has one home. `ask.py`: `answer_from_rows(question, rows, settings)` is the Codex step; `answer_question` (POST /api/ask and the runner) retrieves up to 20 items by FTS5 OR-query over the question's content words (stopwords dropped, prefix on words of 4+ chars), falls back to the 20 most recent in the space, sends them to Codex with the user-authored answer prompt (includes current datetime, task status in headers) and a `{answer, item_ids}` schema, then filters cited ids to the retrieved set. Read-only; about 7 to 10s per question.
**Term expansion (slice 26).** When the question's own words matched nothing, or matched fewer than `MIN_ROWS` (3), *and* `more_to_find` says the database holds more than they matched, a second Codex call (`expand_terms`, its own prompt and `{terms: [...]}` schema) proposes 3 to 5 words and `search` runs again on `terms_query`, which cuts each proposal down to its word characters so nothing that comes back can be read as FTS5 syntax. The question's own matches stay in front of the expanded ones. `CodexError` there is swallowed: a failed expansion leaves the question exactly as well answered as it was before the feature. The `matched_rows` argument is **0 when nothing matched**, not the row count -- the rows returned then are the most recent items, not answers, and counting them made a small database skip the expansion it most needed. The response's `expanded` flag means the proposed terms are what found the answer, not that a second call was made.
**One turn of carry (slice 26).** `AskBody` takes `prior_question` and `prior_item_ids`; those items are fetched in the order given, put at the head of the candidates, and named in a prompt block, so "the second one" has a referent. The server holds no conversation -- the client sends it, and `AskForm` clears it when the answer is dismissed. Term expansion alone cannot do this, which is why the backlog's own worked example needed both halves.
Tests point `TARTIB_AI_COMMAND` at `tests/fake_codex.py`, driven by `FAKE_CODEX_*` env vars, so the subprocess path is exercised for real.
`runner.py` owns an `asyncio.Queue`; capture enqueues via `call_soon_threadsafe`; one consumer task processes captures; startup enqueues every `status='pending'` capture. Errors are written to `proposal_error`. Failed captures are retried (slice 19): a probe every `RETRY_INTERVAL` (15 min) and a pass after every successful classification reset them to pending, at most `MAX_RETRIES` (3) times, counted in `captures.attempts` (migration 0010). Only while the capture's one item is still exactly what the fallback wrote -- note, no space, title, due or reminder, unstarred, open, text unchanged, `proposal_json` null -- so anything a person has started on is never discarded. `AI not configured` is never retried, and the probe does not run with AI off. The reclassify CLI builds its Runner with `retry=False`.
`POST /api/items {shape, space, text, due?}` files an item by hand (slice 20): a capture with `source='web'`, `status='done'` and `direct=1` (migration 0011; a column because `source` is a CHECK constraint SQLite cannot widen without a table rebuild), and one filed item with no proposal. The runner only reads `pending`, retry only `error`, and `reclassify` skips `direct=1`, so the classifier never sees it. A proposal files itself by `store.should_file(space, confidence, threshold, policies)` (slice 20): no space never files; otherwise `spaces.policy` (migration 0012) decides -- `ask` never, `file` always, `auto` by `TARTIB_AUTOFILE_CONFIDENCE`. `GET /api/spaces` returns `policies` beside `spaces`; `PUT /api/spaces/{name}/policy`. A rename carries the policy with the row. `GET /api/sessions/recent?space=&limit=` (slice 20) lists finished sessions newest first with the item's title, text and space; the session card asks for 4 once a session stops, a space page for 20 of its own. `POST /api/items/{id}/redo {reason}` (slice 20, replacing `/reject`): attention items only, 409 with AI off; the reason is appended to `items.feedback` (migration 0013) and committed before the AI call, so it survives a failure (502). `classify(text, context, correction=(earlier_proposal_json, reason))` inserts the correction block just before the text; the first non-question proposal replaces the item's fields and proposal, filed or still waiting by `should_file`. Thoughts (slice 20, migration 0014): `item_thoughts(item_id, body, created_at)`, append-only by a BEFORE UPDATE trigger, deleted with their item (ON DELETE CASCADE), indexed in `thoughts_fts`. `items.thought_count` is kept by an insert trigger, and `items_touch_update` now also skips writes that change `thought_count`, so adding a thought never moves `updated_at` (an open editor would otherwise be refused as stale). Search (`/api/items?q=`) and Ask retrieval append items matched only through their thoughts after the ones their own text matched (`store.items_by_thoughts`); Ask and the brief put each item's thoughts under it in the prompt (`thoughts_for`), and the brief fingerprint includes the thought count. `GET/POST /api/items/{id}/thoughts`. `store.py` is the single write path for filing, shared by the runner, approve, reject, and PATCH. `PATCH /api/items/{id}` takes an optional `expected_updated_at` (slice 19): when present and not equal to the stored `updated_at`, it returns 409 and writes nothing. The item page's text edit and Edit form send it and offer Reload or Overwrite on a 409; row and accordion toggles (star, done) never send it. The check reads then writes on one connection, so two requests landing in the same instant could both pass -- accepted for one user.

## Reminders

`reminders.Reminders` is one 60s task started in the lifespan beside the runner's consumer, and only when both VAPID keys are set and `push.check_key` accepts the private one; a bad key logs an error and leaves the loop off rather than consuming reminders nobody could receive. `tick(now)` takes the clock as an argument, so tests drive it.
Due = `stage='filed' AND status='open' AND reminded_at IS NULL AND remind_at <= now AND remind_at > now - 6h`. Anything older than that 6h grace is marked sent without pushing, so a container down overnight does not replay the night. `reminded_at` is set once per item even when every push fails, guarded on the `remind_at` the tick read so a reminder moved mid-push is not swallowed.
One digest per local day at the first tick past `TARTIB_SUMMARY_TIME`, skipped when both counts are zero but still recording the date in `app_state.digest_date`; a first start after that time writes the day off. Payload is `{title, url}`; `url` is always `/today`.
Its two counts are tasks due today, and **waiting -- both halves**: undecided captures (`stage='attention'`) plus open tasks nobody has touched for `STALE_DAYS`. `store.waiting_counts` is the one owner of that definition, used by the digest and by `/api/attention`, because the digest kept its own copy and counted only the first half, undercounting every morning while the nav badge (`App.tsx`, `items.length + stale.length`) and the Inbox showed both. A task that is both overdue and stale is in both numbers, exactly as it is on both screens. Fixed 2026-09-21.
The payload is `{title, url, tag}`; `tag` is `item-<id>` per reminder and `digest` for the digest, so one notification replaces only itself.
Tapping a reminder on iOS opens Tartib but does not route to the notification's URL. Three approaches were tried and each was confirmed installed on the phone before being ruled out: `WindowClient.navigate()` after `focus()` (does nothing to a frozen client), `postMessage` with a reply and a `navigate()` fallback (a home-screen app is frozen while the worker runs and cannot answer in time), and the worker writing the URL into the shell cache for the app to pick up on waking, read on mount, `visibilitychange`, `focus`, `pageshow` and a short burst of retries. The third is what ships: it is correct, proved on desktop, and costs nothing. Whether iOS dispatches `notificationclick` to the worker at all was never established, and is the first thing to check if this is picked up again.
`push.py` is the transport and the subscriptions table's owner: `broadcast` pushes to every row and deletes any endpoint answering 404 or 410 at once. Any other failure increments `subscriptions.failures` (migration 0006) and the row is dropped after `MAX_FAILURES` (8) in a row, since a push service is allowed a bad minute but not a permanent one; a delivery or a re-subscribe resets the count to 0. A tick charges at most one failure per endpoint however many notifications it sends, or a batch of reminders during one outage would spend every strike and delete a live subscription.
Neither column is evidence that a push arrived. `mark_delivered` only clears a non-zero count and
never touches `last_seen_at`, so a good delivery leaves both looking exactly as they did before;
`failures = 0` equally describes "nothing failed" and "nothing was ever sent". What proves a send
is the caller's own claim (`items.reminded_at`, `sessions.notified_at`) together with the absence
of a strike: `pywebpush` raises `WebPushException` on any non-2xx, and `broadcast` turns that into
a counted failure and a log line.
A failure to subscribe in the browser is not a server problem: `pushManager.subscribe()` talks to
the browser's own push service and the app only POSTs the resulting endpoint afterwards, so
Chrome's "Registration failed - push service error" means it could not register with FCM. The
same VAPID key working on another browser is enough to rule the key out.
`/api/config` hands out `vapid_public` only when a push could actually be delivered: keys that fail `push.check_key` leave the loop off, and the UI must not offer to switch on something that can never fire. `pywebpush` signs with the private key, which never reaches a response, a log line, or an error body. `python -m tartib.vapid` prints a fresh base64url key pair for `.env`.

## Sessions

`sessions(id, item_id NULL, started_at, ends_at, ended_at, outcome, created_at)` (migration 0007) is the pomodoro log. `item_id` is nullable and `ON DELETE SET NULL`: a session is about a task or about nothing, and deleting the task must not erase the time spent. `outcome` is `done | unfinished | abandoned`, null until answered; `done` ticks the task through `store.update_fields`. Only today's counts read this table -- rule 4 forbids the history screen.
`sessions.Sessions` schedules one asyncio timer per running session for that session's own `ends_at`, not on the reminder loop's 60s tick, and re-arms everything unfinished at startup. Announcing a session is its own claim, held on `notified_at` (migration 0008) and separate from closing the row: a page whose countdown reached zero asks the server immediately, and while the two shared a column that read took the notification with it, on the device that was not the one needing to be told. A session stopped by hand or already announced never pushes; nothing is pushed if the end is more than `PUSH_GRACE` (5 min) past. One session runs at a time, but one still owed an outcome does not block the next, and it stops being offered after `OUTCOME_WINDOW` (12 h).
`TARTIB_SESSION_MINUTES` (default 25) is the only length; there is no per-session choice.

## Config (env)

`TARTIB_PASSWORD` (required), `TARTIB_SECRET`, `TARTIB_TZ` (default UTC), `TARTIB_DB_PATH` (default /data/tartib.db), `TARTIB_SPACES` (optional; seeds the spaces table once when it is empty, ignored after that), `TARTIB_STATIC_DIR`, `TARTIB_AI_COMMAND` (default `codex`, `off` disables), `TARTIB_AI_MODEL` (pinned to `gpt-5.6-luna`), `TARTIB_AI_REASONING` (`medium`; sent as a `-c` override), `TARTIB_AI_TIMEOUT` (default 120), `TARTIB_AUTOFILE_CONFIDENCE` (default 0.85), `TARTIB_DUPLICATE_PARK` (default off), `TARTIB_VAPID_PUBLIC`, `TARTIB_VAPID_PRIVATE`, `TARTIB_VAPID_EMAIL` (default `mailto:tartib@localhost`), `TARTIB_SUMMARY_TIME` (default `08:00`, read in `TARTIB_TZ`, validated at load), `TARTIB_SESSION_MINUTES` (default 25, at least 1). `CODEX_HOME` is passed through to the subprocess.

## API

```text
POST   /api/login {password}     POST /api/logout     GET /api/health (public)
POST   /api/capture {text} -> 201 {id}   (a capture id)
GET    /api/captures/{id} -> capture, its items, and the answer if it was a question
GET    /api/today -> {date, items, recent (newest 3 captures), active_space, sessions {total, by_item}}
       items are open filed tasks due today or earlier, starred, with a passed reminder, or
       worked on in a session today
GET    /api/attention -> {items, stale, stale_days}   stale = open filed tasks with updated_at older than 14 days;
       a `split` item carries split {of, whole}
POST   /api/captures/{id}/whole -> the one note replacing a split's pieces; 409 once a piece is touched
GET    /api/recent?limit=50&before=<id> -> {captures, next_before}   keyset paging
GET    /api/items?q=&space=&shape=&status=&limit=&before=     GET /api/items/{id}
PATCH  /api/items/{id}   any editable field, including `text` (the item's own text)
DELETE /api/items/{id}   removes the item; its capture stays
POST   /api/items/{id}/approve [overrides]      POST /api/items/{id}/reject
POST   /api/ask {question, space?} -> {answer, item_ids, items, matched}
GET    /api/spaces      POST /api/spaces {name}      names ^[a-z0-9][a-z0-9-]{0,23}$
PATCH  /api/spaces/{name} {name}   rename, cascading to items and briefs
DELETE /api/spaces/{name}          409 unless the space is empty
GET    /api/spaces/summary -> {spaces:[{name, open, notes, overdue, total, last_activity}], unfiled}
GET    /api/spaces/{space}/brief[?refresh=true] -> {space, text, item_ids, items, updated_at, fresh}
       briefs.py; feeds open tasks + 15 newest notes, cap 30, fixed question;
       404 unknown space, 503 AI off, 502 Codex failure; empty space -> "Nothing here yet." with no call
GET    /api/config -> {tz, spaces, ai, autofile_confidence, vapid_public}   read-only
POST   /api/subscriptions {endpoint, keys:{p256dh, auth}} -> 201 {id}   upserts on endpoint
DELETE /api/subscriptions {endpoint} -> {ok, removed}
GET    /api/subscriptions -> {enabled, count}
POST   /api/sessions {item_id?} -> 201 the session; 409 while one is running
GET    /api/sessions/current -> {state: running | awaiting | null, session, item}
POST   /api/sessions/{id}/stop          stop early; the row is kept and still owed an outcome
POST   /api/sessions/{id}/outcome {outcome}
```

## Frontend shell

`session.tsx` holds the running pomodoro: it renders a countdown against the server's `ends_at`, re-asks whenever the app comes back, and is what `SessionBar` and the start controls read. `SessionBar` sits under the capture bar on every screen and, when a session ends, asks Done / Not finished / Abandoned in the modal (slice 31). It opens once per ended session; Later closes it and the bar keeps an Answer button, and the session put off is kept in `sessionStorage` so neither a page change nor a reload asks again.
Routes: `/` Home (dashboard), `/inbox`, `/inbox/attention` (every waiting item), `/inbox/recent` (paged captures), `/spaces`, `/spaces/:name`, `/settings`, `/items/:id`. Redirects: `/attention`, `/attention/all`, `/recent`, `/today`, `/search`, `/all`. Pill nav Home · Inbox · Spaces · Settings; the Inbox pill stays active across all three inbox routes.
`sw.js` precaches at install rather than waiting for a navigation to fill the cache: it fetches
`index.html`, reads the hashed `/assets/` URLs out of it with a regex, and caches those with the
icons and the manifest. Caching the HTML alone was not enough -- it only names the assets, so the
first offline launch after an install rendered a blank page with a title. Every put is settled
individually, so one missing file cannot fail the install and leave the old worker in place.
It does not call `skipWaiting()` on install. A new worker waits, `update.ts` notices it and the
app offers one line -- "A new version is ready" with Reload -- which posts `tartib:skip-waiting`
and reloads once `controllerchange` fires. Only a handover the user asked for reloads: that event
also fires the first time a worker claims a page that had none. `sw.js` also handles
`pushsubscriptionchange`, re-subscribing with the key `push.ts` leaves at `/__vapid-key` in the
shell cache and re-registering against `/api/subscriptions` with `credentials: "include"`; Safari
does not fire that event, so on the phone it is insurance rather than a fix.
`manifest.webmanifest` has an `id` and a `start_url` of `/` (it was `/today`, a redirect, so every
launch paid one). Since slice 23 there is one theme, so `index.html` carries a single
`theme-color` of `#0d0f12`, the manifest's `background_color` matches it, and no script rewrites
either: the first paint is right before any JavaScript runs, and the splash cannot mismatch.
Since slice 25 the worker also caches **`GET /api/`**, network-first, in a second cache
(`tartib-api-v1`): online is unchanged and the network answers, offline the stored copy does.
`/api/sessions/` is excluded -- a countdown is only true at the moment it is read, and a stale
one is a lie rather than old news. Only `res.ok` is stored, or a 401 would be served back as the
truth for as long as the network stayed down. Each entry is stamped `x-tartib-cached-at` at put
time, which `api()` reports into whatever `tracked()` window is open and `useLoad` turns into the
one line every screen shows; no screen knows how it works. **Activation deletes every cache not
in `KEEP`** -- it was `k !== CACHE`, which would have deleted the API cache on every update.
The editor chunk is pulled down on idle by `TextEditor` (slice 25): the worker only caches assets
it has fetched, so without that a chunk nobody had opened was missing exactly when the network
was, and editing text offline could not work at all. The install still carries nothing extra.
`offline.ts` is the capture queue and the only path a capture takes: `enqueue` writes it to an
IndexedDB store keyed by `client_id`, then `flush` sends what is queued oldest first and stops at
the first one that does not go, so a later capture cannot overtake an earlier one. Ordering lives
in the sort in `list()`, not the store -- `getAll()` returns key order. A 4xx that is not 401 or
429 leaves the queue and surfaces in the toast, since it can never succeed and would wedge
everything behind it; 401 and 5xx stay queued. `watchForReconnect` flushes on `online` and on the
same wake points `push.ts` watches, not Background Sync, which Safari does not have. Both capture
lists render pending rows even when their server load failed, which is exactly when there are any.
`useLoad` owns every screen's load error and says "You're offline." rather than the browser's
"Failed to fetch".
Since slice 25 `offline.ts` is at **IndexedDB v2** and holds a second store, `pending-edits`,
for changes to items that already exist. The upgrade is additive and must stay that way: a phone
coming from v1 may be holding captures typed offline and never sent. An edit's key is
`edit:<item id>` so a second change to the same item **merges into the first** rather than
queueing behind it -- two writes carrying the same `expected_updated_at` would have the first
land and the second refused, the queue conflicting with itself over edits made seconds apart. A
thought cannot merge (the log is append-only) so it takes a key of its own. Four things queue:
status, starred, the item's text, and a thought. A tick or a star queues with **no** base
version, because those go out unchecked when online and a queued one must behave the same.
Unlike the capture queue, a refusal does not stop the replay: captures stop because order is
their guarantee, while edits are already coalesced per item, so one conflict says nothing about
the next. A 409 marks that entry and the item page offers slice 24's strip.
`pending.ts` is the layer reads look through: a queued change is applied to **item fields**
wherever that item appears, and never to counts, tiles or a brief, which the server computes.
Aggregates therefore lag until the queue drains, and the stale line is what explains it.
Sessions, Ask, approve, redo, filing directly, delete and space create/rename/delete stay online
and say so; nothing is ever classified locally, because an earlier build let two devices classify
the same queued capture into two different shapes.
`push.ts` owns the browser side: permission is only ever requested from the Settings button, a subscription is re-minted when it was made with a superseded VAPID key (and the dead row deleted, since that push fails 403 and nothing prunes it), turning off unsubscribes the browser before the server, and opening Settings re-registers an existing subscription so the card cannot read "on" over a row the server dropped. `sw.js` shows the notification and, on a tap, writes the destination into the shell cache and messages the open tab; the app acts on whichever arrives first, when it next wakes. That routing works on desktop and not on iOS, where the app opens but stays where it was. **The files that decide which version runs are sent `Cache-Control: no-cache`** -- `/`, `/index.html`, `/sw.js` and the manifest (since 2026-09-22). Before that Tartib sent none, so a phone's update check could fetch the *old* worker and never offer the reload -- v2.0 only took after the app was deleted and re-added. **The header alone does not reach the browser on `sw.js`**: Cloudflare rewrites it (Deploy, below, "Cloudflare rewrites the browser cache header"). `no-cache` still permits a conditional request, so an unchanged file costs a 304. Vite's hashed assets under `/assets/` are deliberately left cacheable, because their names change with their contents. `sw.js` carries a hand-bumped `SW_VERSION` that Settings displays, because a phone sitting on a stale worker is otherwise invisible. Bump it on every release that changes the app, not only when `sw.js` changes: a browser re-installs a worker only when its bytes differ, so a bundle-only release leaves the old worker active and never offers the reload.
`App` owns: the nav's readouts (the waiting count, which links to the Inbox, and a clock ticking every 30s), which of the two shells renders (`useWide(641)`: header + capture bar + ask bar above it, `TabBar` + `CaptureSheet` + `ItemSheet` below), the `Capture` panel (a bordered box: an auto-growing textarea up to 6 lines on top, then a rule and a control row -- mic via Web Speech API when `SpeechRecognition` exists, a hint, and the one filled button; Enter saves, Shift+Enter newlines), capture polling and the toast, question answers (navigates to Home to show them), the chat bar (`AskBar`) on `/` and `/inbox` only, and keys `c` / `/`.

One component per pattern, each the only owner of its markup:
- `Row` is the list row primitive (leading, title, meta, right, trailing, actions; long-press reveal). `ItemRow` and `RecentList` compose it; no screen writes row markup.
- `Menu` (the "…" dropdown) is **gone** (deleted 2026-09-21, dead since slice 23 and unimported since). Both users -- the item page and the space page -- show their actions as visible pills, and a space's filing policy is an AUTO / ASK / FILE segment on the page. Its `.menu` rules left `styles.css` with it.
- `Tiles` is the stat row on Home: four bordered tiles, each a link to the screen that explains its number, each showing "…" until its data lands rather than a 0 that is about to change.
- `Confirm` is the inline "Delete X? Yes / No" line. `NameForm` is the create-and-rename field, owning its own error state.
- `Card` renders section cards and, with `collapsible`/`open`/`onToggle`, the accordions on the space and item pages.
- `PageHead` (optional eyebrow, title, subtitle) and `BackLink` (history-aware, per-page fallback) carry the header convention in SPEC.
- `Status` exports `Loading`, `ErrorLine`, and `Empty`.
- `ApprovalCard` is one waiting item as a decision; `hotkey` binds Enter. `SearchAsk` is the search field; a question in it goes to `AskForm`, which the ask bar (wide) and the ⊕ sheet (phone) share.
- `TabBar`, `CaptureSheet` and `ItemSheet` are the phone shell (slice 22); `layouts/shared.tsx` holds the space list's pieces (`ItemLead`, `ItemLine`, `SessionLines`, `useSpaceItems`).
Markdown (slice 24) is rendered by `Markdown.tsx` from `marked.lexer()`'s **token stream, emitted
as React elements**. No HTML string is ever built and `dangerouslySetInnerHTML` appears nowhere in
the app -- keep it that way. It is what makes raw HTML in a note, a brief or an Ask answer render
as characters instead of markup, which matters because briefs and answers are written by the
model and marked has had no `sanitize` option since v5; and because every text node is emitted
there, slice 20's search `<mark>` is a branch in that renderer rather than a pass over output.
`safeHref` refuses any scheme but http, https, mailto and in-app paths, so a `javascript:` link
keeps its words and loses its href. The lexer runs with **`breaks: true`**: notes here are typed
rather than authored, and with marked's default a single newline is a space, which would reflow
every note written before that slice. `lex` in `markdown.ts` is the **one** lexer call, shared by
the renderer and `toggleTask`, so the boxes drawn and the boxes ticked are counted the same way.
A continued line keeps its typed indent: marked leaves the whitespace after the newline in the
`br` token's `raw`, and the renderer draws it with `white-space: pre`. An indent on a paragraph's
*first* line is still dropped -- marked strips it before the renderer sees it.
**Checklist boxes are tickable in an item's own text only** (2026-09-22). Only the `- [ ]` /
`- [x]` GFM form is a box. `Markdown` takes an optional `onTick`, and only `TextEditor` passes it;
the brief, Ask answers and thoughts draw boxes disabled. `toggleTask(text, n)` flips the `n`th box
in pre-order (a parent before its nested list). It finds each item by its first line, searching
forward from the offset its top-level block starts at -- top-level `raw`s concatenate back to the
source exactly -- so a box inside a code block is never counted. If it cannot place a box for
certain it returns null, and the tap does nothing. A tick saves at once, not after the debounce. Rendered on the item body, thought entries, Ask answers and
the space brief. Deliberately not rendered where the point is the captured bytes: the original
capture on the item page and `ApprovalCard`. `markdown.ts` holds the helpers that are not React:
`lex`, `toggleTask`, and `flattenFirstLine`, which strips syntax from a row's first line and is
called by all five places that compute a row headline.
The item's text is an editor you tap into, not a mode you enter (slice 24): `TextEditor.tsx`
shows rendered markdown until a tap, then lazy-loads `MarkdownEditor.tsx` -- the only module that
imports CodeMirror, so it is its own **213.86 kB gzip** chunk that a note you merely read never
fetches. Keep it the only importer; a static import from anywhere puts the editor back on the
cold page. `index.html` does not name that chunk, so `sw.js` does not precache it and the import
rejects offline -- caught, so the text stays readable and says why it cannot be edited.
The tap is carried across by **word**, not by coordinates: rendered markdown and its source do
not share a layout, so `posAtCoords` answers about a point that belonged to the other one. The
tap records the Nth occurrence of the word it hit and the editor finds that word again in the
source (`spotFromPoint`, `findSpot`).
Saving is debounced ~2s and flushed on blur, on unmount and on `visibilitychange`/`pagehide`,
with one save in flight at a time. Two things make that survive the way out: the request is
issued **before** any React state update, because a state update first can defer the call past
the renderer's death; and the draft is mirrored to `localStorage` as it is typed, restored on
the way in and cleared once the server has it. That mirror is not belt and braces --
`fetch(..., {keepalive: true})` was measured failing to arrive at all (the server's log line
count was identical either side of the teardown), so the guarantee rests on the draft, not on
keepalive. It is crash safety only: no queue, no replay, none of the offline-edit item's logic.
A stale save (slice 19's 409) asks Reload theirs / Keep mine in a modal that **cannot be
dismissed** (slice 31; a strip above the text until then). It keeps the local words, keeps saying
Unsaved, and pauses the debounce until it is answered -- otherwise it retries into the same
refusal every two seconds. Resolving it remounts the editor, and the outgoing instance must not
flush, or it sends the held draft again and the question returns.
**Every question asks in `Modal.tsx`** (slice 31, the owner's call; until then the app had no
modal anywhere): deleting an item or a space, the session outcome, the stale save, Sign out and
Clear house rules. A native `<dialog>` with `showModal()`, so the browser traps focus and makes
the page inert; Escape and the backdrop call `onClose`, and a modal given none can only be
answered. Focus goes to the panel, not the first button, and back to the opener on close. A
destructive confirm is `ghost danger`, not a filled red button (one filled primary per screen,
and red fill failed contrast before). Not modal, by decision: Inbox decision cards and the
classifier's question buttons (they are the page), the update bar (an offer), "Not saved ·
Retry". `Confirm.tsx` is gone.
**A save must not unmount the editor.** In a space's split view every save bumps `version`, which
refetches the open item, so `ItemPage` shows its skeleton only when it has no item *for this id*;
a refetch of the item already on screen keeps it there. Until 2026-09-22 it showed the skeleton
for any refetch: the editor closed mid-sentence, "Saved" never appeared, and text typed during the
refetch was lost (measured in Chrome).
One primary button class (`.primary`), one ghost, one icon button. The space page is one list with filter pills, so it keeps no collapse state (the old `tartib-space-<name>` key is dead since slice 21).
Tests can steer the fake classifier at runtime through `FAKE_CODEX_REPLY_FILE` (`{"classify": ..., "ask": ...}`); the UI proof injects a fake `SpeechRecognition` to exercise the mic path.

## What browsers do to this app

Found by testing, and none of it changes by deploying:

- Tapping a reminder on iOS opens Tartib but does not route to the notification's URL. Whether
  iOS runs the worker's `notificationclick` at all was never established; what was tried is under
  Reminders above.
- A Chromium-based desktop browser can fail to subscribe to push with "Registration failed - push
  service error": it cannot register with Google's push service (FCM), so
  `pushManager.subscribe()` never reaches Tartib. **Confirmed on 2026-09-22 to be the browser,
  not the app:** it failed in Helix and worked straight away in desktop Safari, with the same
  server and the same VAPID key. Chromium browsers that turn off or never ship Google's push
  services cannot do Web Push at all; nothing on the server can fix that. Worth knowing before
  enabling it anywhere else: one switch covers all three pushers, so every subscribed device
  gets its own buzz for every reminder and every digest.
- `pushsubscriptionchange` is handled (slice 15) but unproved: it needs a push service to retire
  an endpoint, and Safari never fires it.
- The service worker shows nothing when a session ends with the app on screen. Browsers allow
  that only within a budget for `userVisibleOnly` pushes; if Chrome ever says "This site has been
  updated in the background", make that path a silent notification instead of none.
- Voice capture is the browser's own speech recognition, and was proved with an injected engine
  rather than real dictation.

## Deploy

`captain-definition` (schemaVersion 2, pointing at the Dockerfile) exists so anyone else can
one-click this onto CapRover, but it is not the route used: the image is built on the
workstation by `deploy.sh` and pushed to Docker Hub, and CapRover deploys it by image name. The
VPS has the disk but building a Node-plus-two-CLIs image there is what falls over. This machine
is arm64 and the server is not, so `deploy.sh` runs `docker buildx build --platform linux/amd64`
under QEMU; `TARTIB_IMAGE` and `TARTIB_PLATFORM` override the defaults.
**The version number is a rollback label, so it has to be honest about discontinuity.** Decided 2026-09-22: the release after `v1.0` is **`v2.0`**, not `v1.1`. Eight migrations (0010-0017) separate them, and a number one point away invites a flip between them as though it were safe. All eight are additive -- `ADD COLUMN` with a default or nullable, `CREATE TABLE`, `CREATE INDEX`, and the single `DROP TRIGGER` in 0014 recreates it -- so **`v1.0` code would still physically run against schema 17**: inserts fall back on defaults and extra columns are ignored. It would not crash. It would silently orphan thoughts, filing policies, duplicate verdicts, usage rows and the whole AI contract, which is worse than crashing and is exactly what the major bump warns about. Nothing consumes this as an API, so a major bump breaks no contract and costs nothing. The script refuses to
overwrite a tag that already exists, because the tags are immutable versions and there is no
`latest` -- CapRover redeploying the same string could otherwise serve either image.

On CapRover the container's HTTP port must be set to 8000, not the default 80, and there is no
host port mapping: mapping one would bypass nginx, and with it TLS and the `X-Forwarded-Proto`
header the `Secure` session cookie depends on. Force HTTPS is on, so `http://` answers 302. The
persistent directories are `/data` (the database) and `/root/.codex` (the Codex login). The
deployed database is separate from the local one and always has been.
**Cloudflare rewrites the browser cache header on static files** (measured 2026-09-22, on
`v2.1`). The app sends `Cache-Control: no-cache` on `/`, `/index.html`, `/sw.js` and the
manifest (`main.py`), and `/` arrives with it -- but `sw.js` arrives as `max-age=14400`,
because the zone's **Browser Cache TTL** overrides the origin on the extensions Cloudflare
treats as cacheable. So a browser can hold an old worker for four hours whatever the app says,
and a purge does not change it; the fix is Browser Cache TTL set to **Respect Existing
Headers** in the dashboard. There is no Cloudflare CLI or API token on this machine: a purge is
done by hand (Caching -> Purge Cache -> Custom Purge, the `sw.js` URL).

The Codex CLI authenticates with a device code, so `codex login` works over SSH on a headless
server with no browser callback and no credential files to carry. On CapRover it is run inside
the container, because the persistent directory is a labelled volume and the host's own
`~/.codex` is a different directory the container never sees. The mount is read-write so the
CLI's token refresh persists.

**Reading the live app** (first done 2026-09-22). Two routes, both read-only when used as below;
the host, the container name and where the password is kept are in `../state/private.md`.
- The API, with the password as a bearer token (`Authorization: Bearer ...`, which `auth.py`
  accepts for scripts): spaces, items by space, the queue, config, usage. Enough for how things
  are organised, and the same route edits them -- moving items, renaming spaces -- when the owner
  asks for a change.
- A database snapshot over SSH, for what the API does not show (`ai_calls`, `proposal_json`,
  captures): Python's `sqlite3` backup API inside the container against `/data/tartib.db` opened
  `mode=ro`, then `docker cp` out and `scp` here. The live file is never copied while written to.
  The snapshot holds everything the owner keeps, salaries included, so it goes in the session
  scratchpad and is deleted once read, along with the copy left in the server's `/tmp`.

## Maintenance

`python -m tartib.reclassify --all | --attention [--dry-run]` (in Docker: `docker compose exec tartib python -m tartib.reclassify --all`). Deletes the selected captures' items, marks the captures pending, runs the Runner in-process until drained, then carries `starred`/`status` over where a capture still yields one task. Safe with the server up; do not restart the server mid-run. Back up `/data/tartib.db` first (`docker cp tartib-tartib-1:/data/tartib.db …`).

History is not rewritten. It was rewritten three times on 2026-09-18, all before the first push
(one identity, then the domain and private-network setup scrubbed, then a second email address
removed); the repository has been public since, so any further rewrite would be a force-push
over published history. Scrub by commit going forward, never by rewrite.

## Verification commands

```sh
cd backend && uv run pytest -q && uv run ruff check .
cd backend && uv run pytest -m eval        # 8 evals, 56 real calls, ~2m45s. One alone: -k heading
# The evals read the pin out of .env, so they measure the classifier that ships. They did
# not until 2026-09-22, and their numbers before that describe the CLI's default model.
# 12 of what used to be 64 calls were baselines -- what the model does *without* each
# feature -- now measured once into tests/eval_baselines.json and reused. The key carries
# the model, the reasoning effort AND a hash of the captures measured, so editing a
# fixture re-measures rather than comparing against a baseline for captures that no
# longer exist. TARTIB_EVAL_REBASELINE=1 forces a fresh one.
# An eval control must be a capture with ONE obvious answer. Two fence-sitters slipped in
# and both produced false alarms: a control that wobbles measures the wobble, and since
# slice 27 an ambiguous capture legitimately returns no space and a question.
# An eval run that fails fast is the CLI being rate-limited, not a result: 45s for five
# failures against 131s for a clean run. Re-run before believing a failure.
cd frontend && npm run typecheck && npm run build
cd frontend && TARTIB_PASSWORD=... npm run ui   # 18 UI checks, needs the app up and real Chrome
# against a scratch server: it needs at least one space (TARTIB_SPACES) or every check that makes an item fails
docker compose build && docker compose up -d && curl localhost:8000/api/health && docker stats --no-stream
```

## UI language

The phone layout (slice 22) is one breakpoint at 641px in `styles.css` plus `useWide(641)` in `App.tsx`: below it the header, capture bar and ask bar are not rendered and `TabBar` + `CaptureSheet` are; `AskForm` is shared by the bar and the sheet so only one is ever mounted. `--tabbar-h` stacks the ask bar, session card, toast and page padding above the bar.

**The desktop header does not stick.** It did from slice 18 to 2026-09-20, and the cost was that
content scrolled underneath it and hid behind a translucent band -- which is what three rounds of
complaints about "the app bar" actually were. A bar that covers what you are reading is worse
than a bar you scroll past. It is `position: relative` with a solid `--bg` and a 1px bottom
border; phones have no header at all and navigate from the tab bar (slice 22).

**The UI language (slice 23).** The app is set entirely in JetBrains Mono, bundled as self-hosted
woff2 in `frontend/public/fonts`, preloaded from `index.html` and precached by the service worker
-- an offline launch without it falls back to a device mono and every measurement shifts. Base is
14px/1.6, down from 15px/1.5, because mono sets wider than the system sans and the old size
overflowed rows.

**One theme, bronze** (`#0d0f12` ground, `#b98a44` accent), in `:root`. Seven were built on
2026-09-20 and removed the same day; there is no picker, no `data-theme`, no Appearance card and
nothing reading `prefers-color-scheme`. The values are generated by `frontend/tools/themes.py`,
which enforces the contrast floors -- generating them is what caught a `--danger` at 3.93:1 and
an `--accent-2` that paints text while being checked as a decorative star. `themes.md`
in this directory is the record -- the shipped tokens, the derivations and the background --
and a hex in the palette block is never edited by hand.

The page background is two accent glows and a 24px dot grid, `background-attachment: fixed`, with
the glow colour mixed 75% into black -- the raw accent lightens the corner and washes the page
out. Text on the page is measured where the glows overlap, which is the brightest it ever gets;
against the flat colour muted reads 6.32:1 and there it is 4.97:1. The app bar paints no fill,
only its border, so the glow runs through it -- it can, because it does not stick.

The component vocabulary: one shape for controls, a pill with a 1px border, mono uppercase and
tracked, with `.primary` the only filled control on a screen. **Every control is `--control`
tall** -- 32px on a pointer, 44px on a phone -- so a row of them lines up without anyone
measuring; before that token the same page carried 32px, 37px, 39px and 44px controls.
**There are no `⋯` menus.** Actions are visible pills, and a space's filing policy is an
AUTO / ASK / FILE segment on the page. Capture is a panel: the field on top, and under a rule the
mic, a hint and the filled button. The nav's right side carries readouts (waiting count, clock),
never controls. `.chip` and `.tone` share a single
rule -- the tone as text, at 45% as the border, at 12% as the fill -- so a new state is a class,
not a component; `.tone` adds a leading dot. Section labels are mono caps at `.18em`, muted, and
the accent stays in chips, bars and buttons. Every page opens with a breadcrumb (`TARTIB // TODAY`)
through `PageHead`'s `crumb`. The active nav tab, top bar and phone tab bar alike, is a filled
light pill with dark text.

Two floors, not one: 4.5:1 for anything read, 3:1 for what is not text (the star glyph, the
session ring). Text is measured against the surface it actually sits on -- the page, a card, a
card header, a field -- not against `--bg`.

**An eval control must be a capture the classifier places unambiguously**, and since slice 27 it must not treat `None` as failure: an ambiguous capture *correctly* returns no space and a question. A control on the fence measures the wobble, not the thing under test -- "prepare for the exam on Friday" answered work, None and work across three runs and had to be replaced. When an eval fails, check the fixture before reaching for the prompt.

UI checks run headless Chrome through playwright-core from the scratchpad (the Claude in Chrome extension was not connected on 2026-09-17). Contrast is read out of the running app rather than from the stylesheet, and tap targets are measured on the element that receives the tap -- a checkbox's target is the `.tap-box` label wrapping it, not the 18px box.
**Clicking a row near the foot of a list needs `dispatchEvent("click")`, not `click()` and not
`click({ force: true })`.** The ask bar and the phone tab bar are fixed over the last rows, and
`force` only skips the actionability check -- it still dispatches at the element's coordinates,
so the bar eats it. This cost two rounds on slice 25 chasing a queued edit that would not stick;
the queue was right and the click was landing on the ask bar.
Slices up to 25 each built a harness in the scratchpad and threw it away, so nothing could re-run
an earlier slice's checks. That is how slice 24's conflict strip reached a phone 430px wide: its
own checks never had a conflict on screen, and slice 25's harness was the first thing to look.
**Settled in slice 26: they are committed.** `frontend/tools/ui/check.mjs`, run by `npm run ui`,
holds 14 checks over slices 22 to 25, 27, 29 and 31 -- contrast on the surface an element actually sits on,
tap targets, horizontal scroll at 390px (and, since a clipped header hid a space's Delete, every
header control on screen), markdown, tap-to-edit, an offline cold start, and an offline edit
reading "waiting to send", the house-rules editor (Clear asking first), the usage readout --
which also asserts that no money appears while `cost_verified` is false -- the title shown once,
and the delete modal. **F1 and F2** guard two fixes made after `v2.0`: a save not reloading the
note in a split view, and a checklist box ticking where it is drawn. Every check a slice or a
fix proves in a browser goes here, not in a scratch script.
**Two slices are deliberately not covered, and it is not an oversight.** Slice 26's ask-bar follow-up carry and slice 28's "Looks like #N" line and `+ space` button both need a database row the API cannot create -- a prior answer with several items, and an item already carrying a duplicate verdict or a proposed space. They are covered by backend tests and were each looked at once on a 390px viewport. Anyone reading "22 to 29" as a range would assume otherwise, which is why this says it plainly. It needs the app running and `TARTIB_PASSWORD` in the
environment, makes its own items through the API and deletes them, and exits non-zero on a
failure. It caught a real 38x44 tap target on its first run. Two lessons from writing it: a check
that cannot find its control must fail rather than report ok, and `aria-label*="tar"` also matches
"Start session".
