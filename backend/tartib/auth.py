"""One password. Session cookie for the PWA, bearer password for scripts."""

from __future__ import annotations

import hmac

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from itsdangerous import BadSignature, TimestampSigner
from pydantic import BaseModel

from tartib.config import Settings
from tartib.deps import get_settings

COOKIE_NAME = "tartib_session"
MAX_AGE = 60 * 60 * 24 * 30


def _signer(settings: Settings) -> TimestampSigner:
    return TimestampSigner(settings.secret, salt="tartib-session")


def _password_ok(given: str, settings: Settings) -> bool:
    return hmac.compare_digest(given.encode(), settings.password.encode())


def require_auth(request: Request, settings: Settings = Depends(get_settings)) -> None:
    header = request.headers.get("authorization", "")
    if header[:7].lower() == "bearer " and _password_ok(header[7:].strip(), settings):
        return
    cookie = request.cookies.get(COOKIE_NAME)
    if cookie:
        try:
            _signer(settings).unsign(cookie, max_age=MAX_AGE)
            return
        except BadSignature:
            pass
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
    if not _password_ok(body.password, settings):
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
