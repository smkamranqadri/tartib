# Slice 16: the public repo (approved 2026-09-18)

The remote exists and is empty: `https://github.com/smkamranqadri/tartib.git`, public, created
2026-09-17. This slice is everything that has to be true before the first push, because most of
it is far more awkward afterwards.

## Step 1 — one identity, and no secrets

The history carries two people: 39 commits under a second name and address, and 15 as
`Muhammad Kamran <smkamranqadri@yahoo.com>`. `git filter-repo` maps both to
**Muhammad Kamran <smkamranqadri@yahoo.com>**, messages and order untouched. The other address
is not written down here: naming it in the file that explains why it was removed would publish
exactly what the rewrite took off the commits.

That rewrites every SHA, and KIS cites SHAs on purpose: the step-by-step proof for slices 11 and
12 lives in commit messages rather than in State, and `state/current.md`,
`intent/slice-12-pomodoro.md` and `intent/history.md` point at `34ab011`, `fc75770`, `e2e31cc`,
`91d7a22` and `970348e`. Updating those citations is part of this step, not a follow-up, or the
proof on record points at nothing. After the first push a second rewrite means a force-push, so
this happens once, now.

~~Move the test VAPID key into a fixture.~~ **Void, 2026-09-18.** It was never hard-coded:
`test_reminders.py` line 20 is `TEST_PUBLIC, TEST_PRIVATE = generate()`, a fresh pair per run.
The claim came from reading a grep hit without reading the line above it, and it is wrong. There
is no key in the tests and nothing to scrub.

Then a full-history secret scan while the repo is still private, and a check that
`smkamranqadri@yahoo.com` is verified on the GitHub account — unverified, and none of the
rewritten commits link to you. `gh auth refresh -h github.com -s user` makes that checkable from
here; the GitHub email settings page answers it without the scope.

## Step 2 — documentation that is true

The README describes a version of Tartib that no longer exists. It says "Three screens", lists
Today / Ask bar / Needs Attention / All, and its environment table is missing the VAPID trio,
`TARTIB_SUMMARY_TIME`, `TARTIB_SESSION_MINUTES` and `TARTIB_STATIC_DIR`. It also still implies
`TARTIB_SPACES` is the source of truth for spaces, when since migration 0004 it only seeds an
empty table once. Rewritten against SPEC: four screens, the current routes, reminders, pomodoro,
the full table, and a plain note about what the auth actually is.

`.env.example` gains `TARTIB_SESSION_MINUTES` and is diffed against `config.py` in both
directions — nothing missing, nothing listed that the code does not read.

`CONTRIBUTING.md`: how to run it, the three verification commands, how `kis/` and the slice files
work, and the part that matters to anyone opening a pull request — rule 4 is a hard constraint,
so a patch adding tags, projects, or a pomodoro history screen is declined on principle rather
than on taste. Better to say so than to let someone write it first.

Screenshots into `docs/screenshots/`, driven by playwright-core at 390px and 1280px in both
themes: Home, Inbox, a space with its brief, the item page, Settings. **Against a throwaway
database seeded with invented captures.** The real one holds real notes, and a screenshot of a
personal capture system is a screenshot of someone's errands.

## Found while building step 2

- `.env.example` was missing `TARTIB_DB_PATH`, `TARTIB_SESSION_MINUTES` and
  `TARTIB_STATIC_DIR`. `CLAUDE_CODE_OAUTH_TOKEN` is in it and not in `config.py`, which is
  correct: the Claude CLI reads it from the environment itself.
- The README's "Not planned" section still listed pomodoro and push notifications, both of
  which have shipped. That is the kind of line that makes a reader distrust the rest of a
  document.
- It also claimed 15 eval fixtures. There are 16.
- The API list was checked against the running app's OpenAPI rather than transcribed: every
  route claimed exists, and nothing is missing.
- Memory claim checked too: 41.26MiB of the 512MB limit at rest.

## Found while scrubbing, 2026-09-18

`.git/filter-repo/commit-map` is **cumulative across runs**: after a second pass its keys are
still the *original* pre-first-rewrite SHAs, mapping straight to the current ones, not the SHAs
that existed when that pass started. Looking up the intermediate SHAs finds nothing, which reads
like the map is broken when it is simply keyed from further back. If this is ever done a third
time, map from the originals.

## Step 3 — push

Push to the remote, confirm the rendered README and that nothing was blocked. `kis/`, `.agents/`,
`.claude/` and `.pi/` all go public: the project memory is the interesting part of this repository
for anyone else, since it is where the reasons live.

## Out of scope

CI, issue templates, a release. The release is cut at the end of slice 17, as v1.0, once it is
proved running somewhere real — a tag on code that has only ever run on one laptop marks nothing.

## Proof

- `git log --format='%ae' | sort -u` prints one address, and `%an` one name.
- Every commit hash cited anywhere in `kis/` resolves under `git cat-file -e`.
- A full-history secret scan is clean.
- Every variable in `config.py` appears in `.env.example` and the README table, and nothing
  appears in either that `config.py` does not read.
- Screenshots contain no real capture text.
- The repository is public, the push was not blocked, and the README renders.

## Files

`README.md`, `.env.example`, `CONTRIBUTING.md` (new), `docs/screenshots/` (new),
`backend/tests/test_reminders.py`, `kis/state/current.md`, `kis/intent/slice-12-pomodoro.md`,
`kis/intent/history.md`.

Review: `/security-review` before the push. It is the last moment the repository is private.

## Status
- [x] filter-repo to one identity, update the KIS commit citations, secret scan, confirm the
      email is verified on GitHub (2026-09-18; the test-key item was void)
- [x] README, .env.example, CONTRIBUTING, screenshots from a seeded database (2026-09-18)
- [ ] push
