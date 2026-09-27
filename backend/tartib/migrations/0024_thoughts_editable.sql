-- Slice 37: a thought can be edited and deleted, in the app and over MCP, by the owner's
-- decision on 2026-09-27. 0014 made the log append-only; an edit is now marked instead, so the
-- log still says which entries are not as first written.
DROP TRIGGER item_thoughts_append_only;
ALTER TABLE item_thoughts ADD COLUMN edited_at TEXT;

CREATE TRIGGER thoughts_fts_au AFTER UPDATE OF body ON item_thoughts
BEGIN
  INSERT INTO thoughts_fts (thoughts_fts, rowid, body) VALUES ('delete', old.id, old.body);
  INSERT INTO thoughts_fts (rowid, body) VALUES (new.id, new.body);
END;

-- The count followed inserts only. Changing thought_count does not move `updated_at` (0014).
CREATE TRIGGER item_thoughts_count_ad AFTER DELETE ON item_thoughts
BEGIN
  UPDATE items SET thought_count = thought_count - 1 WHERE id = old.item_id;
END;
