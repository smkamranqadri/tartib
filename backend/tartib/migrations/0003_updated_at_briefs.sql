-- Internal change timestamp on items, kept by triggers. Never proposed, never edited.
ALTER TABLE items ADD COLUMN updated_at TEXT;
UPDATE items SET updated_at = COALESCE(classified_at, created_at);
CREATE INDEX items_updated_at ON items (updated_at);

CREATE TRIGGER items_touch_insert AFTER INSERT ON items
WHEN NEW.updated_at IS NULL
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;

-- Fires for every update that did not itself set updated_at, so the touch below does not recurse.
CREATE TRIGGER items_touch_update AFTER UPDATE ON items
WHEN NEW.updated_at IS OLD.updated_at
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;

-- One cached AI brief per space. Not an item.
CREATE TABLE briefs (
  space       TEXT PRIMARY KEY,
  fingerprint TEXT NOT NULL,
  text        TEXT NOT NULL,
  item_ids    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
