-- Slice 33: links between items, written `[[Title]]` in the text.
--
-- Both tables are an index of what the text says, kept by store.index_links on every text write
-- and rebuilt at startup, so neither is ever the only copy of anything. They live apart from
-- `items` on purpose: writing a key onto the item row would fire the touch trigger and move
-- `updated_at` for bookkeeping nobody did.

-- Every item's first line, flattened and case-folded (the key) and as shown (the title).
CREATE TABLE item_keys (
  item_id INTEGER PRIMARY KEY REFERENCES items(id) ON DELETE CASCADE,
  key     TEXT NOT NULL,
  title   TEXT NOT NULL
);
CREATE INDEX item_keys_key ON item_keys (key);

-- One row per distinct `[[…]]` in an item's text, by the key it names.
CREATE TABLE item_links (
  source_id INTEGER NOT NULL REFERENCES items(id) ON DELETE CASCADE,
  target    TEXT NOT NULL,
  PRIMARY KEY (source_id, target)
);
CREATE INDEX item_links_target ON item_links (target);
