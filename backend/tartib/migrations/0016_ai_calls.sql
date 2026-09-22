-- Slice 29. One row per AI call. Tartib runs a subprocess for every capture and has never known
-- anything about it: not how long it took, not what it consumed, not that the subscription limit
-- has stopped work repeatedly.
--
-- Rows rather than running totals, because rows can answer "what did the classifier context add
-- when it shipped" and a counter cannot. Nothing is altered; this table is additive.
--
-- `capture_id` is null for an Ask, which belongs to no capture. It is not a foreign key on
-- purpose: deleting a capture must not erase the record that the work was paid for.
CREATE TABLE ai_calls (
  id                       INTEGER PRIMARY KEY,
  created_at               TEXT    NOT NULL,
  kind                     TEXT    NOT NULL,   -- classify | ask | terms
  model                    TEXT,               -- null when unpinned: the CLI chose
  capture_id               INTEGER,
  ok                       INTEGER NOT NULL DEFAULT 1,
  failure                  TEXT,               -- the CLI's own words, kept verbatim
  reason                   TEXT,               -- usage_limit | timeout | other
  resets_at                TEXT,               -- as reported, when the reason is usage_limit
  duration_ms              INTEGER NOT NULL DEFAULT 0,
  input_tokens             INTEGER NOT NULL DEFAULT 0,
  cached_input_tokens      INTEGER NOT NULL DEFAULT 0,
  cache_write_input_tokens INTEGER NOT NULL DEFAULT 0,
  output_tokens            INTEGER NOT NULL DEFAULT 0,
  reasoning_output_tokens  INTEGER NOT NULL DEFAULT 0,
  total_tokens             INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX ai_calls_created ON ai_calls (created_at);
CREATE INDEX ai_calls_capture ON ai_calls (capture_id);
