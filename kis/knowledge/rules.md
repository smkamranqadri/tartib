# Rules

Hard constraints. Do not relax without an explicit decision recorded here.

1. Stored `raw_text` is immutable. Classification proposes fields around it and never rewrites it.
2. Capture never waits on AI. A capture request returns as soon as the row is stored.
3. One AI adapter only, OpenAI-compatible, configured from env. No second provider.
4. No projects, no tags, no pomodoro, no push notifications, no "ask the AI" feature.
5. One password from env. No user accounts, no signup.
6. Memory budget is 512MB for the whole compose stack.
