-- Slice 32: a star that Pick for me set, as opposed to one a person set. The next pick removes
-- only these; any star set by hand clears the mark (store.update_fields), so it is never taken.
ALTER TABLE items ADD COLUMN picked_at TEXT;
