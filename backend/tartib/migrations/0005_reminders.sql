-- Web Push: one reminder per item, the browsers we may push to, and a place for the
-- digest's last-sent date.
ALTER TABLE items ADD COLUMN reminded_at TEXT;

-- A reminder firing is not a human touch, so it must not reset `updated_at` and hide the
-- item from the stale list in Needs Attention. The editing path sets `updated_at` itself
-- when it clears `reminded_at`, which is a real edit.
DROP TRIGGER IF EXISTS items_touch_update;
CREATE TRIGGER items_touch_update AFTER UPDATE ON items
WHEN NEW.updated_at IS OLD.updated_at AND NEW.reminded_at IS OLD.reminded_at
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;

-- Everything already due counts as sent, so the first tick after this deploy is silent
-- instead of replaying every reminder the database has ever held.
UPDATE items SET reminded_at = strftime('%Y-%m-%dT%H:%M:%SZ', 'now')
WHERE remind_at IS NOT NULL AND remind_at <= strftime('%Y-%m-%dT%H:%M:%SZ', 'now');

CREATE INDEX items_remind_pending ON items (remind_at) WHERE reminded_at IS NULL;

CREATE TABLE subscriptions (
  id           INTEGER PRIMARY KEY,
  endpoint     TEXT NOT NULL UNIQUE,
  p256dh       TEXT NOT NULL,
  auth         TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  last_seen_at TEXT NOT NULL
);

-- Small internal key/value. Today it holds `digest_date`, the last day the digest went out.
CREATE TABLE app_state (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
