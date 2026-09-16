-- Captures are stored once; items are classifier output that reference a capture.
CREATE TABLE captures (
  id            INTEGER PRIMARY KEY,
  raw_text      TEXT NOT NULL,
  source        TEXT NOT NULL DEFAULT 'api' CHECK (source IN ('web', 'api', 'migrated')),
  created_at    TEXT NOT NULL,
  status        TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'done', 'error')),
  error         TEXT,
  answer_json   TEXT,
  classified_at TEXT
);
CREATE INDEX captures_status ON captures (status);
CREATE INDEX captures_created_at ON captures (created_at);

CREATE TRIGGER captures_raw_text_immutable BEFORE UPDATE OF raw_text ON captures
BEGIN
  SELECT RAISE(ABORT, 'raw_text is immutable');
END;

-- One capture per existing item, same id. Unclassified placeholders become pending captures.
INSERT INTO captures (id, raw_text, source, created_at, status, classified_at)
SELECT id, raw_text, 'migrated', created_at,
       CASE WHEN stage = 'inbox' THEN 'pending' ELSE 'done' END,
       classified_at
FROM items;

DROP TRIGGER items_fts_ai;
DROP TRIGGER items_fts_ad;
DROP TRIGGER items_fts_au;
DROP TRIGGER items_raw_text_immutable;
DROP TABLE items_fts;

CREATE TABLE items_new (
  id             INTEGER PRIMARY KEY,
  capture_id     INTEGER NOT NULL REFERENCES captures (id),
  raw_text       TEXT NOT NULL,
  space          TEXT,
  shape          TEXT NOT NULL DEFAULT 'note' CHECK (shape IN ('task', 'note')),
  stage          TEXT NOT NULL DEFAULT 'attention' CHECK (stage IN ('attention', 'filed')),
  created_at     TEXT NOT NULL,
  title          TEXT,
  due            TEXT,
  remind_at      TEXT,
  starred        INTEGER NOT NULL DEFAULT 0,
  status         TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'done')),
  proposal_json  TEXT,
  proposal_error TEXT,
  classified_at  TEXT,
  CHECK (stage <> 'filed' OR space IS NOT NULL)
);

-- 'inbox' was never a real space. Those items now wait for a human. Placeholder rows that
-- were still unclassified are dropped; their captures are pending and get re-classified.
INSERT INTO items_new (id, capture_id, raw_text, space, shape, stage, created_at, title, due,
                       remind_at, starred, status, proposal_json, proposal_error, classified_at)
SELECT id, id, raw_text,
       CASE WHEN space = 'inbox' THEN NULL ELSE space END,
       shape,
       CASE WHEN space = 'inbox' THEN 'attention' ELSE stage END,
       created_at, title, due, remind_at, starred, status, proposal_json, proposal_error,
       classified_at
FROM items
WHERE stage <> 'inbox';

DROP TABLE items;
ALTER TABLE items_new RENAME TO items;

CREATE INDEX items_capture ON items (capture_id);
CREATE INDEX items_stage ON items (stage);
CREATE INDEX items_space ON items (space);
CREATE INDEX items_due ON items (due);
CREATE INDEX items_remind_at ON items (remind_at);

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

INSERT INTO items_fts (items_fts) VALUES ('rebuild');
