-- Owner-authored context starts empty; schema changes never infer or seed it.
ALTER TABLE spaces ADD COLUMN description TEXT NOT NULL DEFAULT '';
ALTER TABLE spaces ADD COLUMN description_updated_at TEXT NOT NULL DEFAULT '';
