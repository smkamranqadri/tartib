-- A push that fails for any reason other than 404 or 410 leaves the row in place: the push
-- service may simply be having a bad minute. Counting the failures means an endpoint that is
-- broken for good is eventually dropped instead of retried on every tick forever.
ALTER TABLE subscriptions ADD COLUMN failures INTEGER NOT NULL DEFAULT 0;
