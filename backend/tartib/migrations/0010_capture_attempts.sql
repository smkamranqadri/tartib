-- A capture that failed to classify is retried by the runner once Codex answers again. Each retry
-- is counted here so one that fails every time -- an unusable reply, say, rather than an outage --
-- stops after a few goes and waits for a person instead of costing a call every probe forever.
ALTER TABLE captures ADD COLUMN attempts INTEGER NOT NULL DEFAULT 0;
