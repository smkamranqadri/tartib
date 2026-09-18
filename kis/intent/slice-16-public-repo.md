# Slice 16: the public repo (approved 2026-09-18)

The remote exists and is empty: `https://github.com/smkamranqadri/tartib.git`, public, created
2026-09-17. This slice is everything that has to be true before the first push, because most of
it is far more awkward afterwards.

## Step 1 — one identity, and no secrets

The history carries two people: 39 commits as `a second name and address` and 15
as `Muhammad Kamran <smkamranqadri@yahoo.com>`. `git filter-repo` maps both to
**Muhammad Kamran <smkamranqadri@yahoo.com>**, messages and order untouched.

That rewrites every SHA, and KIS cites SHAs on purpose: the step-by-step proof for slices 11 and
12 lives in commit messages rather than in State, and `state/current.md`,
`intent/slice-12-pomodoro.md` and `intent/history.md` point at `ecd2000`, `8a897ad`, `7d8ffd6`,
`6c5c16b` and `9a80a28`. Updating those citations is part of this step, not a follow-up, or the
proof on record points at nothing. After the first push a second rewrite means a force-push, so
this happens once, now.

`backend/tests/test_reminders.py` hard-codes a VAPID private key. It is generated and harmless,
but GitHub push protection can block a push over it, and a scanner flagging the repo on day one
is a poor first impression. It moves into a fixture that generates a pair at test time.

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
- [ ] filter-repo to one identity, update the KIS commit citations, test key into a fixture,
      secret scan, confirm the email is verified on GitHub
- [ ] README, .env.example, CONTRIBUTING, screenshots from a seeded database
- [ ] push
