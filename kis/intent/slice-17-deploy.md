# Slice 17: harden, publish the image, deploy (approved 2026-09-18)

Tartib runs on a laptop behind a private network, so reminders stop whenever the lid closes. That is the
one thing that keeps it from being a daily driver. It moves to the CapRover VPS that already
hosts everything else, at `https://the domain`, with CapRover taking the certificate
from Let's Encrypt — which means the auth has to be worth exposing first.

## Step 1 — a login that can be on the internet

One shared password, and every `/api/*` route also accepts it as `Authorization: Bearer` so the
iOS Shortcut needs no login flow. Rate limiting `POST /api/login` alone would be theatre: an
attacker guesses against `/api/today` with a bearer header and never touches the login route. The
backoff therefore hangs off the password comparison itself, wherever it is reached from.

Global, with no IP, as decided -- and Cloudflare in front of CapRover adds a second hop to
trust, which is one more reason not to. Behind them the client address only arrives in
`X-Forwarded-For` and `CF-Connecting-IP`, and trusting that header wrongly either collapses every attacker into one
bucket or lets one attacker lock out the whole app. One password is one account, so a global
count is coherent and there is no header to get wrong.

- Counters live in the existing `app_state` table, not in memory, so a restart is not a free
  reset.
- Four failures cost nothing. From the fifth, 429 with `Retry-After` and a window that grows and
  caps at five minutes. A success resets the count to zero.
- During a block, a correct password is refused too. Checking it would hand an attacker an
  unlimited oracle that says which guess was right, which is the thing being prevented.
- A valid signed cookie never consults the counter. So a phone or browser already signed in keeps
  working through an attack; what a sustained attack costs you is fresh logins and Shortcut
  captures, for up to five minutes at a time. That is the price of not trusting the proxy header,
  and it was chosen with that known.

### The session cookie is not Secure behind the proxy

Found 2026-09-18 by checking rather than reading. `auth.py` sets `secure=request.url.scheme ==
"https"`, and the Dockerfile already runs uvicorn with `--proxy-headers` -- but that option
trusts `X-Forwarded-Proto` only from `forwarded-allow-ips`, which defaults to `127.0.0.1`. Behind
CapRover the peer is the Docker network, not localhost, so the header is ignored, the app sees
`http`, and the cookie goes out without `Secure`. Proved locally: a login carrying
`X-Forwarded-Proto: https` came back `HttpOnly; Max-Age=2592000; Path=/; SameSite=lax` and no
`Secure`.

On a public HTTPS site that is a session cookie a downgrade can carry in the clear. Two things
both have to be true, or it stays broken quietly:

- `FORWARDED_ALLOW_IPS` set so uvicorn trusts the proxy. `*` is defensible here and only here,
  because CapRover reaches the container over an internal network and the port is not published
  anywhere else -- the header is trustworthy exactly because nothing untrusted can set it.
- Cloudflare's SSL mode on Full (strict), with CapRover holding a real certificate. On Flexible,
  Cloudflare talks to the origin over plain HTTP, `X-Forwarded-Proto` is honestly `http`, and
  fixing uvicorn changes nothing.

Proved by tests before anything is deployed, and re-checked on the live domain in step 4.

## Step 2 — the image

The VPS has disk but building there is the problem, so the image is built here and pushed to
`smkamranqadri/tartib` on Docker Hub, public. Tags are immutable versions -- `v1.0`, then `v1.1`
and so on -- and there is no `latest`: CapRover deploys by image name, and a tag whose contents
changed underneath it can redeploy to the same string and quietly serve either image. A version
per deploy also makes a rollback a choice from a list rather than a rebuild.
This Mac is arm64 and the VPS is amd64, so it is
`docker buildx build --platform linux/amd64` under QEMU: slow, accepted, and the known cost of
not using CI. If it becomes intolerable the same buildx line moves into GitHub Actions on
`ubuntu-latest`, which is native amd64 and free for a public repository — the escape hatch, not
the plan.

- Confirm the VPS architecture with `uname -m` before building for it.
- A short deploy script so build, push and redeploy is one command, documented in the README.
- A `captain-definition` in the repository as well. It is not the route used here, but it makes
  the project one-click deployable for anyone else on CapRover, which is a real reason to have
  published it.
- The image is public and holds no secrets: configuration is runtime env and the Codex login is
  a mounted directory.
- Confirm the image boots on amd64 before touching the VPS.

## Step 3 — the app on CapRover

Deployed by image name. A persistent directory at `/data`, another at `/root/.codex` with the
Codex login copied into it — the browser OAuth flow expects a localhost callback, so the files
are copied rather than a login performed there.

`CLAUDE_CODE_OAUTH_TOKEN` is set as well. Both CLIs are already in the image running identical
prompts, so if the copied Codex login ever objects to the VPS's address, filing keeps working and
promoting Claude to primary is an env change with no code. Without it the failure is invisible:
no error, just an Inbox slowly filling with `proposal_error` notes.

Every variable from `.env` moves into the CapRover panel, plus the container memory limit that
`docker-compose.yml` used to carry, HTTPS with force-redirect, and a health check on
`/api/health`. `docker-compose.yml` stays for local development.

The database starts empty. The Mac's is archived to `a local backup directory` and not migrated.

## Step 4 — prove it, protect it, tag it

- Log in at `https://the domain` on a valid certificate. Six wrong passwords return
  429, and the right one works after the window.
- The session cookie comes back with `Secure` on it. This is the one that will pass by default
  if nobody looks, because everything else about the login still works without it.
- A capture typed on the phone over cellular files itself within about fifteen seconds: the
  copied Codex login working from that address.
- Break Codex deliberately; a capture still files through the Claude fallback.
- The phone re-enables reminders against the new origin. Every existing subscription is bound to
  the old origin and is dead; `push.py` prunes them on the first 404 or 410. A reminder
  buzzes.
- A session started on the phone buzzes once when it ends with the app closed. This is slice 12's
  outstanding proof, re-run where it will actually live.
- A cron on the VPS copies `/data/tartib.db` off the persistent directory, and one of its files
  is restored once. A persistent directory is not a backup, and a backup nobody has restored is
  a rumour.
- Tag `v1.0` and cut the GitHub release.

## Risks and assumptions

- Assumes the VPS is amd64; step 2 checks rather than assumes.
- The QEMU cross-build may be slow enough to be annoying on every deploy. GitHub Actions is the
  escape.
- The copied Codex login may re-authenticate on a new address, silently. The Claude fallback is
  the mitigation and proving it is an acceptance check, not a hope.
- A global backoff means anyone hammering the login slows yours too. Accepted, and bounded by the
  cookie exemption above.
- The bearer token is the password. One leaked Shortcut configuration is full access. Use a long
  random password.

## Files

`backend/tartib/auth.py`, `deps.py`, `store.py`, `backend/tests/test_auth.py`,
`captain-definition` (new), a deploy script (new), `README.md`, `.env.example`.

Review: `/security-review` on step 1, `/code-review` on the diff before step 2 builds it.

## Status
- [ ] global login backoff covering the bearer path, counters in app_state, tests
- [ ] FORWARDED_ALLOW_IPS so the session cookie is Secure behind the proxy
- [ ] buildx amd64, push to Docker Hub, captain-definition, deploy script
- [ ] CapRover app: persistent dirs, Codex login, Claude token, env, HTTPS, health, empty DB
- [ ] prove on real devices, backup cron with a restore, tag v1.0
