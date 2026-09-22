-- Slice 31, 2026-09-22. The title is the text's first line. Until now a task's title was a
-- separate field the classifier wrote, shown above the text and editable in one place only;
-- from here the store derives it from line one on every write (`store.title_of`). Existing
-- tasks whose title says something their first line does not get it added as line one, a
-- blank line between -- the same thing filing does to a new task. The capture is untouched.
--
-- "Says something different" ignores case and a leading `#`, `-`, `*` or `>`: "Buy milk" over
-- "buy milk" would only repeat it. A task that differs only in case, or has no title, takes
-- its first line as the title instead, so the column agrees with what the rows show.
--
-- None of this is an edit anyone made, so it must not move `updated_at`: the Stale list reads
-- it, and slice 30's Keep as one reads "untouched since filed" as updated_at = classified_at.
-- The touch trigger is dropped for the rewrite and re-created exactly as 0014 left it.
DROP TRIGGER items_touch_update;

UPDATE items
SET raw_text = trim(title) || char(10) || char(10) || raw_text,
    title = trim(title)
WHERE shape = 'task' AND title IS NOT NULL AND trim(title) != ''
  AND lower(trim(title)) != lower(ltrim(trim(
        substr(ltrim(raw_text, char(10) || char(13) || ' '), 1,
               instr(ltrim(raw_text, char(10) || char(13) || ' ') || char(10), char(10)) - 1)
      ), '#*>- '));

UPDATE items
SET title = ltrim(trim(
      substr(ltrim(raw_text, char(10) || char(13) || ' '), 1,
             instr(ltrim(raw_text, char(10) || char(13) || ' ') || char(10), char(10)) - 1)
    ), '#*>- ')
WHERE shape = 'task'
  AND (title IS NULL OR trim(title) = ''
       OR title IS NOT ltrim(trim(
            substr(ltrim(raw_text, char(10) || char(13) || ' '), 1,
                   instr(ltrim(raw_text, char(10) || char(13) || ' ') || char(10), char(10)) - 1)
          ), '#*>- '));

CREATE TRIGGER items_touch_update AFTER UPDATE ON items
WHEN NEW.updated_at IS OLD.updated_at AND NEW.reminded_at IS OLD.reminded_at
  AND NEW.thought_count IS OLD.thought_count
BEGIN
  UPDATE items SET updated_at = strftime('%Y-%m-%dT%H:%M:%fZ', 'now') WHERE id = NEW.id;
END;
