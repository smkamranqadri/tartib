# Tartib (ترتیب)

Open-source personal capture system. Single user. MIT license.

You type anything into one box. It lands in an inbox. A background AI call proposes how to file it. Confident proposals are filed automatically; the rest wait for a human decision. Three screens, nothing else.

Stage: greenfield, September 2026. Nothing is built yet.

## Stack

- Backend: FastAPI (Python).
- Frontend: React + Vite, shipped as a PWA.
- Storage: SQLite with FTS5 for search.
- Deployment: one `docker-compose.yml`. Must run inside 512MB RAM.
- Auth: one password, read from env `TARTIB_PASSWORD`.
- AI: one OpenAI-compatible chat endpoint, base URL, key, and model read from env.

## AI contract

One function: `classify(text, context) -> proposal`.

Proposal fields: `shape`, `space`, `title`, `due`, `remind_at`, `confidence`.

It runs in the background after capture has already been stored. Capture never waits on it.
