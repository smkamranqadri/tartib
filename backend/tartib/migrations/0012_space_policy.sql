-- How a space takes what the classifier proposes for it. `auto` is the global confidence rule;
-- `ask` never files on its own, whatever the confidence; `file` always files when the proposal
-- names this space, whatever the confidence. Enforced by the runner, not asked of the prompt: a
-- prompt can be ignored.
ALTER TABLE spaces ADD COLUMN policy TEXT NOT NULL DEFAULT 'auto' CHECK (policy IN ('auto', 'ask', 'file'));
