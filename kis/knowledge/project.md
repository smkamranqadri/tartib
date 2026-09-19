# Tartib (ترتیب)

Open-source personal capture system. Single user. MIT license.

You type anything into one box. It is stored once, verbatim, then a background AI call turns it into one or more items and files them into your own spaces. Confident proposals file themselves; the rest wait for you in the Inbox. A capture that is a question is answered from your notes instead of filed. Four screens: Home, Inbox, Spaces, Settings.

Stage: v1.0, released and deployed 2026-09-18 from a public repository, and in daily use.

## Stack

FastAPI + SQLite (FTS5) backend, React + Vite PWA frontend, one Docker container, one password from env, classification by the Codex CLI, the only classifier (the login mounted or made on the host). Details in `technical.md`.
