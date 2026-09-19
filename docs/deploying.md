# Deploying Tartib

Everything needed to run this somewhere other than your laptop. The [README](../README.md) covers what Tartib is and how to try it locally.

## Security

One password, one user. Every `/api` route accepts that password as a bearer token as well as the session cookie, which is what makes shortcuts and scripts easy and also means the password is the only thing between anyone and everything. There is no second factor. Put it behind HTTPS and treat the password as the whole security model.

Guessing is slowed by a global backoff: four failures are free, then each further attempt gets `429` with a `Retry-After`, in a window that doubles from 30 seconds and stops at five minutes. It hangs off the password comparison rather than the login route, so it covers the bearer header too — otherwise guesses would simply move to a route nobody was watching. It is global rather than per-IP because behind a proxy the client address only arrives in a header, and one password is one account. While blocked, a correct password is refused as well: checking it would say which guess was right. A browser already holding a valid session cookie is never affected, so nobody can log you out by hammering the door.

The session cookie is marked `Secure` only when the app sees an HTTPS request. Behind a reverse proxy that needs uvicorn to trust `X-Forwarded-Proto`; the image runs with `--proxy-headers --forwarded-allow-ips "*"`, which is safe precisely because nothing reaches the port except the proxy in front of it.

## Secrets and logins

Five things need generating or authenticating, and none of them live in this repository.

**The password, and the cookie signing key.**

```sh
openssl rand -base64 24    # TARTIB_PASSWORD
openssl rand -hex 32       # TARTIB_SECRET
```

Set `TARTIB_SECRET` explicitly even though it is optional. Unset, it is derived from the password, so changing the password later silently logs out every device.

**Push keys**, if you want reminders. Tartib generates its own pair:

```sh
cd backend && uv run python -m tartib.vapid     # from a checkout
docker run --rm <your-image> python -m tartib.vapid   # or from the image, no checkout needed
```

It prints the three lines to paste. They are a matched pair: a subscription is bound to the public key that made it, so replacing one half breaks every existing subscription with a `403` — which is neither `404` nor `410`, so nothing prunes the dead row and the UI keeps claiming reminders are on. Without both keys the reminder loop never starts, and `/api/config` withholds the public key so the interface will not offer to switch on something that cannot fire.

**The Codex login.** Locally, `codex login` on the host is enough: compose mounts `~/.codex` into the container.

On a server there is no browser, but the CLI authenticates with a device code, so this works over SSH:

```sh
docker exec -it <container> codex login
```

It has to be a persistent directory at `/root/.codex`, or the login is wiped by the next deploy. Two ways, and the difference matters:

- **A named volume.** Then the login must be made *inside the container*, as above. The host's own `~/.codex` is a different directory the container never sees.
- **A bind mount** of the host path — `/home/ubuntu/.codex:/root/.codex`, say. Then log in on the host and the container reads the same files. Note the container runs as root and Codex rewrites its credential on token refresh, so those files end up owned by `root`.

Either way the mount is read-write, because the refresh has to go somewhere.

**When Codex fails.** There is no second classifier. A Codex outage or usage limit means captures pile up in Needs Attention with `proposal_error` set. Nothing is lost and nothing is announced — you find out by noticing the Inbox growing.

## Environment

| Variable | Required | Default | Meaning |
| --- | --- | --- | --- |
| `TARTIB_PASSWORD` | yes | | The one password. |
| `TARTIB_SECRET` | no | derived from password | Cookie signing key. Set it to keep sessions across password changes. |
| `TARTIB_TZ` | no | `UTC` | IANA zone that defines "today" and resolves "tomorrow" in captures. |
| `TARTIB_SPACES` | no | | Comma-separated. Seeds the spaces table once, when empty. Ignored after that. |
| `TARTIB_DB_PATH` | no | `/data/tartib.db` | SQLite file. |
| `TARTIB_STATIC_DIR` | no | set by the image | Where the built frontend is served from. |
| `TARTIB_AI_COMMAND` | no | `codex` | Command that runs the Codex CLI. `off` disables classification. |
| `TARTIB_AI_MODEL` | no | | Passed as `codex --model`. Unset uses Codex's default. |
| `TARTIB_AI_TIMEOUT` | no | `120` | Seconds allowed per classification. |
| `TARTIB_AUTOFILE_CONFIDENCE` | no | `0.85` | Proposals at or above this are filed without asking. |
| `TARTIB_VAPID_PUBLIC` | no | | Web Push key pair. Without both keys the reminder loop does not run. |
| `TARTIB_VAPID_PRIVATE` | no | | Generate with `cd backend && uv run python -m tartib.vapid`. |
| `TARTIB_VAPID_EMAIL` | no | `mailto:tartib@localhost` | A contact the push service can reach. |
| `TARTIB_SUMMARY_TIME` | no | `08:00` | One daily digest, at the first tick past this time in `TARTIB_TZ`. |
| `TARTIB_SESSION_MINUTES` | no | `25` | Every pomodoro is this long. No per-session choice. |

## Deploying to a server

There is a `captain-definition`, so a [CapRover](https://caprover.com) instance can build and deploy this from the repository directly. That is not the route used here: the image carries a Node runtime and two AI CLIs, and building it on a small VPS is the part that falls over. It is built on a workstation and pushed instead.

```sh
./deploy.sh v1.0        # buildx for linux/amd64, push to Docker Hub
```

Then in CapRover, the app's Deployment tab, "Deploy via ImageName". Tags are immutable versions and there is no `latest`: CapRover deploys by image name, and a tag whose contents changed underneath it can redeploy to the same string and serve either image with nothing to tell them apart. A version per deploy also makes a rollback a choice from a list instead of a rebuild.

Set `TARTIB_IMAGE` for your own Docker Hub namespace, and `TARTIB_PLATFORM` if your server is not amd64. The app needs two persistent directories: `/data` for the database, and `/root/.codex` if you want classification, which means getting a Codex login onto the server.

## Re-run the classifier

After changing spaces or the prompt, rebuild items from their captures:

```sh
docker cp tartib-tartib-1:/data/tartib.db ./tartib-backup.db     # first
docker compose exec tartib python -m tartib.reclassify --all        # or --attention, add --dry-run to preview
```

Done and starred carry over when a capture still produces one task. Manual edits to space, title, or dates do not.
