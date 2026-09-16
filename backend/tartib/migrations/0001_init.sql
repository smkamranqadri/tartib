CREATE TABLE items (
  id             INTEGER PRIMARY KEY,
  raw_text       TEXT NOT NULL,
  space          TEXT NOT NULL DEFAULT 'inbox',
  shape          TEXT NOT NULL DEFAULT 'note' CHECK (shape IN ('task', 'note')),
  stage          TEXT NOT NULL DEFAULT 'inbox' CHECK (stage IN ('inbox', 'attention', 'filed')),
  created_at     TEXT NOT NULL,
  title          TEXT,
  due            TEXT,
  remind_at      TEXT,
  starred        INTEGER NOT NULL DEFAULT 0,
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  proposal_json  TEXT,
  proposal_error TEXT,
  classified_at  TEXT
);

CREATE INDEX items_stage ON items (stage);
CREATE INDEX items_space ON items (space);
CREATE INDEX items_due ON items (due);
CREATE INDEX items_remind_at ON items (remind_at);

-- raw_text is immutable. Enforced here so no code path can drift.
CREATE TRIGGER items_raw_text_immutable BEFORE UPDATE OF raw_text ON items
BEGIN
  SELECT RAISE(ABORT, 'raw_text is immutable');
END;

CREATE VIRTUAL TABLE items_fts USING fts5(
  raw_text, title,
  content = 'items', content_rowid = 'id',
  tokenize = 'unicode61 remove_diacritics 2'
);

CREATE TRIGGER items_fts_ai AFTER INSERT ON items
BEGIN
  INSERT INTO items_fts (rowid, raw_text, title) VALUES (new.id, new.raw_text, new.title);
END;

CREATE TRIGGER items_fts_ad AFTER DELETE ON items
BEGIN
  INSERT INTO items_fts (items_fts, rowid, raw_text, title)
  VALUES ('delete', old.id, old.raw_text, old.title);
END;

CREATE TRIGGER items_fts_au AFTER UPDATE OF title ON items
BEGIN
  INSERT INTO items_fts (items_fts, rowid, raw_text, title)
  VALUES ('delete', old.id, old.raw_text, old.title);
  INSERT INTO items_fts (rowid, raw_text, title) VALUES (new.id, new.raw_text, new.title);
END;
