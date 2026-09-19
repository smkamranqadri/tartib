-- Disagreeing with a proposal takes a reason and asks the classifier again (slice 20, replacing
-- Reject). The reasons are kept here, one dated line each: the only record of why the first
-- answer was wrong. The item's text is never touched by it (rule 1).
ALTER TABLE items ADD COLUMN feedback TEXT;
