"""One password. Session cookie for the PWA, bearer password for scripts.

Guessing is slowed by a global backoff rather than a per-IP one. Behind a proxy the client
address only arrives in a header, and trusting that header wrongly either collapses every
attacker into one bucket or lets one attacker lock out the whole app. One password is one
account, so a global count is coherent and there is no header to get wrong.

The backoff hangs off the password comparison, not off the login route. Every `/api` route also
accepts the password as a bearer token, so rate limiting `/api/login` alone would be theatre:
guesses would simply move to `/api/today` with a header.
"""

from __future__ import annotations

import hmac
import sqlite3
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, TimestampSigner
from pydantic import BaseModel

from tartib import db
from tartib.clock import as_utc_iso, parse_iso, utcnow
from tartib.config import Settings
from tartib.deps import get_settings
from tartib.store import clear_state, get_state, set_state

COOKIE_NAME = "tartib_session"
MAX_AGE = 60 * 60 * 24 * 30

# Four failures cost nothing: a typo, a stale saved password, a fat-fingered Shortcut.
FREE_ATTEMPTS = 4
# Then a window that doubles, from 30s, and stops at five minutes. Long enough to make guessing
# pointless, short enough that locking yourself out is an inconvenience rather than an outage.
BLOCK_BASE = timedelta(seconds=30)
BLOCK_CAP = timedelta(minutes=5)
FAILURES_KEY = "login_failures"
BLOCKED_UNTIL_KEY = "login_blocked_until"


def _signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.secret, salt="tartib-session")


def _password_ok(given: str, settings: Settings) -> bool:
    return hmac.compare_digest(given.encode(), settings.password.encode())


def _conn(settings: Settings) -> sqlite3.Connection:
    """The throttle opens its own short-lived connection instead of taking `get_db` as a
    dependency. A dependency would open one for every request on every route; this opens one
    only when a password is actually being checked, which a signed-in browser never does."""
    return db.connect(settings.db_path)


def blocked_seconds(conn: sqlite3.Connection, now: datetime) -> int:
    """How long the door stays shut. Zero means it is open."""
    until = get_state(conn, BLOCKED_UNTIL_KEY)
    if not until:
        return 0
    left = (parse_iso(until) - now).total_seconds()
    return max(0, int(left + 0.999))  # round up: 0 must mean open, not "nearly open"


def record_failure(conn: sqlite3.Connection, now: datetime) -> None:
    failures = int(get_state(conn, FAILURES_KEY) or 0) + 1
    set_state(conn, FAILURES_KEY, str(failures))
    if failures <= FREE_ATTEMPTS:
        return
    window = min(BLOCK_BASE * 2 ** (failures - FREE_ATTEMPTS - 1), BLOCK_CAP)
    set_state(conn, BLOCKED_UNTIL_KEY, as_utc_iso(now + window))


def record_success(conn: sqlite3.Connection) -> None:
    clear_state(conn, FAILURES_KEY, BLOCKED_UNTIL_KEY)


def check_password(given: str, settings: Settings, now: datetime | None = None) -> bool:
    """The one place a password is compared. While blocked it refuses without looking at the
    password at all: checking it would hand an attacker an oracle saying which guess was right,
    which is the thing being prevented. The cost is that your own correct password is refused
    too, for at most five minutes, and only for a fresh login or a bearer call -- a browser
    already holding a valid cookie never reaches here."""
    now = now or utcnow()
    conn = _conn(settings)
    try:
        seconds = blocked_seconds(conn, now)
        if seconds:
            raise HTTPException(
                status_code=429,
                detail="too many failed attempts",
                headers={"Retry-After": str(seconds)},
            )
        if _password_ok(given, settings):
            record_success(conn)
            return True
        record_failure(conn, now)
        # The attempt that trips the block is told so, rather than getting a plain 401 and
        # leaving you to discover the lock on the next try.
        seconds = blocked_seconds(conn, now)
        if seconds:
            raise HTTPException(
                status_code=429,
                detail="too many failed attempts",
                headers={"Retry-After": str(seconds)},
            )
        return False
    finally:
        conn.close()


def require_auth(request: Request, settings: Settings = Depends(get_settings)) -> None:
    # The cookie is tried first so that a signed-in browser never touches the throttle, even if
    # it also happens to carry a stale Authorization header. A signature cannot be usefully
    # guessed, so it is not something the backoff needs to defend.
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        try:
            _signer(settings).unsign(cookie, max_age=MAX_AGE)
            return
        except BadSignature:
            pass
    header = request.headers.get("authorization", "")
    if header[:7].lower() == "bearer " and check_password(header[7:].strip(), settings):
        return
    raise HTTPException(status_code=401, detail="authentication required")


router = APIRouter(prefix="/api")


class LoginBody(BaseModel):
    password: str


@router.post("/login")
def login(
    body: LoginBody,
    request: Request,
    response: Response,
    settings: Settings = Depends(get_settings),
) -> dict:
    if not check_password(body.password, settings):
        raise HTTPException(status_code=401, detail="wrong password")
    token = _signer(settings).sign(b"ok").decode()
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response) -> dict:
    response.delete_cookie(COOKIE_NAME, path="/")
    return {"ok": True}
