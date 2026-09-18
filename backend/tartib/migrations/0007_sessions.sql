-- Pomodoro sessions. Logging only, by rule 4: nothing reads this but today's counts, and
-- there is no history screen to build on it.
CREATE TABLE sessions (
  id         INTEGER PRIMARY KEY,
  -- A session is about a task, or about nothing. ON DELETE SET NULL because deleting the
  -- task must not erase the fact that the time was spent.
  item_id    INTEGER REFERENCES items(id) ON DELETE SET NULL,
  started_at TEXT NOT NULL,
  ends_at    TEXT NOT NULL,
  -- When it actually stopped: `ends_at` when it ran out, earlier when it was stopped by hand.
  ended_at   TEXT,
  outcome    TEXT CHECK (outcome IS NULL OR outcome IN ('done', 'unfinished', 'abandoned')),
  created_at TEXT NOT NULL
);

CREATE INDEX sessions_started_at ON sessions (started_at);
-- The two questions asked on every load: is one running, and is one waiting for an outcome.
CREATE INDEX sessions_open ON sessions (ends_at) WHERE outcome IS NULL;
