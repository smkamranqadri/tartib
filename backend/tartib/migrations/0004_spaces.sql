-- Spaces are data now. Seeded from TARTIB_SPACES by the app on first start after this migration.
CREATE TABLE spaces (
  name       TEXT PRIMARY KEY,
  position   INTEGER NOT NULL DEFAULT 0,
  created_at TEXT NOT NULL
);

-- A filed item's text belongs to the user. The capture keeps the original, still immutable.
DROP TRIGGER items_raw_text_immutable;

DROP TRIGGER items_fts_au;
CREATE TRIGGER items_fts_au AFTER UPDATE OF raw_text, title ON items
BEGIN
  INSERT INTO items_fts (items_fts, rowid, raw_text, title)
  VALUES ('delete', old.id, old.raw_text, old.title);
  INSERT INTO items_fts (rowid, raw_text, title) VALUES (new.id, new.raw_text, new.title);
END;
