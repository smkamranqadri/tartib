"""Web Push: the subscriptions a browser registered, and one send that tells the caller
only whether the subscription is still alive."""

from __future__ import annotations

import json
import logging
import sqlite3

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from tartib.auth import require_auth
from tartib.clock import utcnow_iso
from tartib.config import Settings
from tartib.deps import get_db, get_settings

log = logging.getLogger("tartib.push")

# Consecutive failures before an endpoint is written off. A push service can be briefly
# unreachable, so one bad answer means nothing; eight in a row means the device is gone.
MAX_FAILURES = 8

router = APIRouter(prefix="/api", dependencies=[Depends(require_auth)])


class Gone(Exception):
    """The push service says this subscription no longer exists: drop the row."""


def subscriptions(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute("SELECT * FROM subscriptions ORDER BY id").fetchall()


def save_subscription(conn: sqlite3.Connection, endpoint: str, p256dh: str, auth: str) -> int:
    """One row per endpoint. Re-subscribing refreshes the keys instead of adding a row, and
    clears the failure count: the browser just told us this endpoint is alive."""
    now = utcnow_iso()
    conn.execute(
        "INSERT INTO subscriptions (endpoint, p256dh, auth, created_at, last_seen_at)"
        " VALUES (?, ?, ?, ?, ?)"
        " ON CONFLICT (endpoint) DO UPDATE SET p256dh = excluded.p256dh,"
        " auth = excluded.auth, last_seen_at = excluded.last_seen_at, failures = 0",
        (endpoint, p256dh, auth, now, now),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM subscriptions WHERE endpoint = ?", (endpoint,)).fetchone()
    return int(row["id"])


def drop_subscription(conn: sqlite3.Connection, endpoint: str) -> int:
    cur = conn.execute("DELETE FROM subscriptions WHERE endpoint = ?", (endpoint,))
    conn.commit()
    return cur.rowcount


def mark_delivered(conn: sqlite3.Connection, sub_id: int) -> None:
    """A delivery clears the history. The count is consecutive failures, not lifetime ones."""
    conn.execute("UPDATE subscriptions SET failures = 0 WHERE id = ? AND failures != 0", (sub_id,))
    conn.commit()


def mark_failed(conn: sqlite3.Connection, sub_id: int) -> int:
    """Count one failure and drop the subscription once it has failed MAX_FAILURES times in a
    row. Returns the new count; 0 means the row is gone."""
    conn.execute("UPDATE subscriptions SET failures = failures + 1 WHERE id = ?", (sub_id,))
    row = conn.execute("SELECT failures FROM subscriptions WHERE id = ?", (sub_id,)).fetchone()
    failures = int(row["failures"]) if row else 0
    if failures >= MAX_FAILURES:
        conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
        conn.commit()
        return 0
    conn.commit()
    return failures


def check_key(settings: Settings) -> None:
    """Raises if the configured private key is not usable. A truncated key would otherwise
    fail once per push, be logged as one broken browser, and quietly consume every reminder."""
    from py_vapid import Vapid02

    Vapid02.from_string(private_key=settings.vapid_private)


def send(row: sqlite3.Row, payload: dict, settings: Settings) -> None:
    """Sign and deliver one notification. Raises Gone when the endpoint is dead, and
    swallows nothing else: the caller logs and moves on to the next subscription."""
    from pywebpush import WebPushException, webpush  # heavy import, only on a real send

    try:
        webpush(
            subscription_info={
                "endpoint": row["endpoint"],
                "keys": {"p256dh": row["p256dh"], "auth": row["auth"]},
            },
            data=json.dumps(payload),
            vapid_private_key=settings.vapid_private,
            vapid_claims={"sub": settings.vapid_email},
            ttl=600,
            timeout=10,
        )
    except WebPushException as e:
        status = getattr(e.response, "status_code", None)
        if status in (404, 410):
            raise Gone(str(status)) from e
        raise


def broadcast(conn: sqlite3.Connection, payload: dict, settings: Settings, sender=send) -> int:
    """Push to every subscription. An endpoint the push service disowns is deleted at once; any
    other failure is counted, and counted out after MAX_FAILURES in a row. One broken browser
    must not hold up the rest. Returns the sends that worked."""
    delivered = 0
    for row in subscriptions(conn):
        try:
            sender(row, payload, settings)
        except Gone:
            drop_subscription(conn, row["endpoint"])
            log.info("dropped a subscription the push service no longer knows")
        except Exception as e:  # a push is best effort: one broken browser is not fatal
            failures = mark_failed(conn, row["id"])
            if failures:
                log.warning("push failed (%d in a row): %s", failures, e)
            else:
                log.warning("dropped a subscription after %d failures: %s", MAX_FAILURES, e)
        else:
            mark_delivered(conn, row["id"])
            delivered += 1
    return delivered


class SubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=1, max_length=200)
    auth: str = Field(min_length=1, max_length=200)


class SubscriptionBody(BaseModel):
    model_config = ConfigDict(extra="ignore")  # the browser's toJSON() carries more than we need

    endpoint: str = Field(min_length=1, max_length=1000)
    keys: SubscriptionKeys


@router.post("/subscriptions", status_code=201)
def subscribe(
    body: SubscriptionBody,
    conn: sqlite3.Connection = Depends(get_db),
) -> dict:
    """Register this browser for reminders. Called again on every load, so it upserts."""
    sub_id = save_subscription(conn, body.endpoint, body.keys.p256dh, body.keys.auth)
    return {"id": sub_id}


class UnsubscribeBody(BaseModel):
    endpoint: str = Field(min_length=1, max_length=1000)


@router.delete("/subscriptions")
def unsubscribe(body: UnsubscribeBody, conn: sqlite3.Connection = Depends(get_db)) -> dict:
    """Turning reminders off in Settings. Unknown endpoints are already in the wanted state."""
    return {"ok": True, "removed": drop_subscription(conn, body.endpoint)}


@router.get("/subscriptions")
def count(
    conn: sqlite3.Connection = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    """What Settings shows: whether this install can push at all, and how many browsers listen."""
    row = conn.execute("SELECT COUNT(*) AS n FROM subscriptions").fetchone()
    return {"enabled": settings.push_enabled, "count": row["n"]}
