-- Slice 29 follow-up, 2026-09-22. `ai_calls` recorded what a call cost and nothing about what
-- it contained, so "did the context block earn its tokens" was unanswerable no matter how much
-- was captured.
--
-- The reason this matters: the *parts* of the prompt are capped -- the space context at 4000
-- characters, house rules at 2000 -- but the whole is not. Examples are capped at five entries
-- and candidates at eight items, neither with a character limit, so the prompt can grow with
-- the database and nothing would say so.
--
-- Additive, and only ever written at the moment of the call; none of it can be backfilled.
ALTER TABLE ai_calls ADD COLUMN prompt_chars INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_calls ADD COLUMN candidates_n INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_calls ADD COLUMN examples_n INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_calls ADD COLUMN corrections_n INTEGER NOT NULL DEFAULT 0;
ALTER TABLE ai_calls ADD COLUMN house_rules INTEGER NOT NULL DEFAULT 0;
