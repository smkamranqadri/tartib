-- A capture typed with no network is queued in the browser and sent when there is one. If that
-- send half-succeeds -- stored, but the response never arrives -- the retry must not become a
-- second capture, a second classifier call and a second set of items. `client_id` is minted by
-- the browser before the first attempt and identifies the capture rather than the request.
--
-- Nullable, and unique only among the rows that have one: every capture made before this, and
-- every one made by curl or a Shortcut, has none. SQLite's unique index allows repeated NULLs,
-- which is exactly the shape wanted here.
ALTER TABLE captures ADD COLUMN client_id TEXT;
CREATE UNIQUE INDEX captures_client_id ON captures(client_id);
