# Security

## Reporting a problem

Please report security problems privately through GitHub's
[security advisories](https://github.com/smkamranqadri/tartib/security/advisories/new), not in a
public issue. Expect a first reply within a week. Fixes go into the next release; there are no
backports to older tags.

## The model

Tartib is single user. One password, set in `TARTIB_PASSWORD`, opens everything: the app, and
every `/api` route as a bearer token. The deploy guide's
[security section](docs/deploying.md#security) describes it in full. In short:

- Guessing is slowed by a global backoff that also covers the bearer header.
- The session cookie is signed, and marked `Secure` behind HTTPS.
- `/mcp` exists only when `TARTIB_MCP_TOKEN` (at least 32 characters) is set, and only that token
  opens it.
- The classifier runs the Codex CLI as a subprocess in an ephemeral, read-only sandbox. Your text
  is sent to it, and therefore to the model provider behind your Codex login. Nothing else leaves
  the container except Web Push, if you enable it.
- Model-written Markdown is rendered without raw HTML or remote fetches.

## In scope

A way to read or change data without the password or the MCP token, to bypass the backoff, to
make the classifier or Ask write something it should not, or to make the browser load remote
content from item text.

## Out of scope

A weak password you chose, running without HTTPS, and anything that needs the password already.
