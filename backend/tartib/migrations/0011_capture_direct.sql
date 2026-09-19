-- An item can be filed by hand from a space page, with the shape and space already known and no
-- classifier involved. It still gets a capture -- every item has one, and what was typed is kept
-- the same way -- marked here so nothing ever sends it to the classifier: the reclassify CLI
-- would otherwise replace a hand-filed task with whatever the model thought of the text. A
-- column, not a new `source` value, because `source` is a CHECK constraint SQLite cannot widen
-- without rebuilding a table that items reference.
ALTER TABLE captures ADD COLUMN direct INTEGER NOT NULL DEFAULT 0;
