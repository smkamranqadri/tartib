-- Slice 28. Two additive columns, because an item waiting in Needs Attention now has three
-- possible reasons -- no space, low confidence, or a suspected duplicate -- and a row that
-- cannot say which is a row that says nothing.
--
-- `duplicate_of` is the item this one looks like. It is recorded whether or not parking is
-- switched on (TARTIB_DUPLICATE_PARK), so the verdict can be judged against real captures
-- before it is ever allowed to hold anything back.
--
-- `wait_reason` is a short code, not display text: the client already has the matched item and
-- writes the sentence itself.
ALTER TABLE items ADD COLUMN duplicate_of INTEGER REFERENCES items(id) ON DELETE SET NULL;
ALTER TABLE items ADD COLUMN wait_reason TEXT;
