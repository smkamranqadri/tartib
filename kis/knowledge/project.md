# Tartib (ترتیب)

Open-source personal capture system. Single user. MIT license.

You type anything into one box. It lands in an inbox. A background AI call proposes how to file it. Confident proposals are filed automatically; the rest wait for a human decision. Three screens, nothing else.

Stage: v0.1 built 2026-09-17, unreleased. No git remote yet.

## Stack

FastAPI + SQLite (FTS5) backend, React + Vite PWA frontend, one Docker container, one password from env, one OpenAI-compatible AI endpoint from env. Details in `technical.md`.
