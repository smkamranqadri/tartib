-- A thought section on each item: the person's own thinking, kept apart from the item's text,
-- as an append-only log of dated entries -- one field where the last edit wins loses the
-- thinking that came before it. Searched, and read by Ask and the space brief.
CREATE TABLE item_thoughts (
  id         INTEGER PRIMARY KEY,
  item_id    INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  body       TEXT NOT NULL CHECK (length(trim(body)) > 0),
  created_at TEXT NOT NULL
);
CREATE INDEX item_thoughts_item ON item_thoughts (item_id, id);

-- Append-only: an entry, once written, stays as written.
CREATE TRIGGER item_thoughts_append_only BEFORE UPDATE ON item_thoughts
BEGIN
  SELECT RAISE(ABORT, 'thoughts are append-only');
END;

CREATE VIRTUAL TABLE thoughts_fts USING fts5(body, content='item_thoughts', content_rowid='id');
CREATE TRIGGER thoughts_fts_ai AFTER INSERT ON item_thoughts
BEGIN
  INSERT INTO thoughts_fts (rowid, body) VALUES (new.id, new.body);
END;
CREATE TRIGGER thoughts_fts_ad AFTER DELETE ON item_thoughts
BEGIN
  INSERT INTO thoughts_fts (thoughts_fts, rowid, body) VALUES ('delete', old.id, old.body);
END;

-- The count rows show, kept with the item so every list has it without a join.
ALTER TABLE items ADD COLUMN thought_count INTEGER NOT NULL DEFAULT 0;
CREATE TRIGGER item_thoughts_count AFTER INSERT ON item_thoughts
BEGIN
  UPDATE items SET thought_count = thought_count + 1 WHERE id = new.item_id;
END;

-- Adding a thought is not an edit of the item: it must not move `updated_at`, or an editor left
-- open beside the thought log would have its next save refused as stale. Same narrowing 0005
-- made for `reminded_at`.
DROP TRIGGER items_touch_update;
CREATE TRIGGER items_touch_update AFTER UPDATE ON items
WHEN NEW.updated_at IS OLD.updated_at AND NEW.reminded_at IS OLD.reminded_at
  AND NEW.thought_count IS OLD.thought_count
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;
