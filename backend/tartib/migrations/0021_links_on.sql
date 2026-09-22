-- Slice 33 phase C: whether a classify call was made with link proposals on. The switch changes
-- the prompt, so the duplicate and house-rules data gathered before it must be told apart.
ALTER TABLE ai_calls ADD COLUMN links_on INTEGER NOT NULL DEFAULT 0;
