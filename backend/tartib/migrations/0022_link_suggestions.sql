-- Slice 34: links suggested for items already filed, by `python -m tartib.suggest_links`.
-- Their own table, never `proposal_json`: that holds the classifier's first reading, which the
-- examples learn from. A pair is suggested once; `skipped` is how it is never suggested again.
CREATE TABLE link_suggestions (
  item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  target_id  INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  state      TEXT    NOT NULL DEFAULT 'pending' CHECK (state IN ('pending', 'kept', 'skipped')),
  created_at TEXT    NOT NULL,
  PRIMARY KEY (item_id, target_id)
);
CREATE INDEX link_suggestions_target ON link_suggestions (target_id);

-- What each item's text was when it was last asked about, so a run does not pay again for an
-- item that got nothing and has not changed since. Keyed by a hash of the text, not a time:
-- `updated_at` moves for things that change nothing the model reads.
CREATE TABLE link_asks (
  item_id   INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  text_hash TEXT    NOT NULL,
  asked_at  TEXT    NOT NULL
);
