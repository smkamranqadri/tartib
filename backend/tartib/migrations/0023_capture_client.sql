-- Slice 35: which agent wrote a capture through MCP ("claude-code"), shown as "via claude-code"
-- on its items. NULL for everything the owner wrote. A column rather than a new `source` value:
-- `source` has a CHECK constraint, and SQLite can only change one by rebuilding the table that
-- every item points at.
ALTER TABLE captures ADD COLUMN client TEXT;
