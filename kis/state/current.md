# Current

- Branch: `main`, local only.
- Task: none. One-time re-classification of all live captures done 2026-09-17 with the new prompt and configured spaces.
- Command: `cd backend && uv run pytest -q` / `docker compose exec tartib python -m tartib.reclassify --all`.
- Blocker: none. Claude fallback inside Docker still needs `CLAUDE_CODE_OAUTH_TOKEN`.
- Next: user decides. 12 items wait in Needs Attention, 10 of them because no configured space fits (e.g. movies, books, social media, messaging people). Adding a space or two to `TARTIB_SPACES` and re-running `--attention` would clear most of them.

## Proof (2026-09-17, reclassify)

- `uv run pytest -q`: 75 passed (reclassify: rebuild, flag carry-over, attention scope, dry run).
- Live, in the container, backup taken first (`backup/tartib-pre-reclassify.db` in the session scratchpad): 23 captures re-classified in 269s, 0 errors, 1 answered. 35 items now (was 22): 23 filed, 12 waiting. 7 captures split into 2 to 4 items. Flags carried over on 3 single-task captures.
