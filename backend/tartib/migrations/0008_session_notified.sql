-- Ending a session and announcing it are two different claims. They used to be one: the first
-- write to `ended_at` won the right to push, so any read that tidied a finished session -- a
-- page whose countdown had just hit zero, asking the server what now -- silently took the
-- notification with it, on the device that was not the one that needed telling.
ALTER TABLE sessions ADD COLUMN notified_at TEXT;
