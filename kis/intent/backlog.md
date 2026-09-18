# Backlog

Two lists: work that is approved and waiting for a plan, then candidates that are not required
and may never happen. How Tartib is built lives in `../knowledge/technical.md`.

Approved on 2026-09-18 and planned, in this order, before anything below:
slice 15 (`slice-15-pwa.md`), slice 16 (`slice-16-public-repo.md`), slice 17
(`slice-17-deploy.md`). They are what makes Tartib a daily driver: it installs and captures
offline, the repository is public, and it runs somewhere that is awake when the laptop is not.

Approved on 2026-09-17, not yet planned. Each gets a plan file when it comes up, and both now
sit behind 15 to 17:

- **13 presentation** — markdown on the item page, note bodies and briefs; a live editor that
  styles as you type and never rewrites the stored bytes; eight themes in Settings; delete the
  redundant Edit link in `frontend/src/components/ItemRow.tsx` (the one with `aria-label="Edit"`;
  it was line 79 when this was written and line numbers drift).
- **14 AI contract** — the classifier prompt editable and stored as an override with the
  default shipped in code; Ask becomes continuous.

Unscheduled candidates:

- Image is 1.62GB (Node runtime + Codex CLI + Claude CLI + uvicorn extras, plus cryptography and aiohttp via pywebpush since slice 11). Not a stated constraint (memory is, and runtime is 42MiB). A slimmer route: download the Codex release binary instead of npm. Worth more after slice 17: every deploy cross-builds this image under QEMU, where size is time.
- The AI fallback fails slowly when it cannot authenticate. Proved on the deployed app
  2026-09-18: with `TARTIB_AI_COMMAND` broken deliberately and no `CLAUDE_CODE_OAUTH_TOKEN` set,
  Codex failed instantly and correctly, then the Claude leg burned the full `TARTIB_AI_TIMEOUT`
  of 120s before giving up -- `stdin` is already DEVNULL, so it was authenticating, not waiting
  for input. Captures queue serially, so a burst during a real outage stalls for minutes and
  files nothing. The fallback exists to cover an outage quickly and currently does the opposite.
  Either give the fallback leg its own shorter timeout, or check the token is present before
  spending a capture on it.
- Automatic retry for `proposal_error` items after a Codex outage or usage-limit block. Today they wait for a human. Seen for real on 2026-09-17 when the ChatGPT usage limit hit mid-deploy.
- Codex takes about 10s per item on the host. Fine for personal volume; a burst of captures queues serially.
- Ask retrieval is keyword-only FTS5. The cheap next step is letting Codex propose 3 to 5 search terms first, still no embeddings. Slice 14 needs this, not just wants it: a follow-up like "what about the second one?" has no content words, so the OR-query returns nothing.
