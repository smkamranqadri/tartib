from tests.conftest import PASSWORD


def test_health_is_public(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"ok": True, "ai": False, "fallback": False}


def test_capture_requires_auth(client):
    assert client.post("/api/capture", json={"text": "x"}).status_code == 401


def test_bearer_password(client):
    r = client.post(
        "/api/capture", json={"text": "x"}, headers={"Authorization": f"Bearer {PASSWORD}"}
    )
    assert r.status_code == 201
    r = client.post("/api/capture", json={"text": "x"}, headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_login_cookie_flow(client):
    assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    r = client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 200
    assert "tartib_session" in client.cookies
    assert client.post("/api/capture", json={"text": "x"}).status_code == 201
    client.post("/api/logout")
    assert client.post("/api/capture", json={"text": "x"}).status_code == 401


# --- the global backoff -------------------------------------------------------------------
#
# Global and not per-IP: behind a proxy the client address only arrives in a header, and one
# password is one account, so counting per-account is coherent and there is nothing to spoof.


def wrong(client, n=1):
    last = None
    for _ in range(n):
        last = client.post("/api/login", json={"password": "wrong"})
    return last


def test_four_failures_are_free_then_the_door_shuts(client):
    for _ in range(4):
        assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
    r = client.post("/api/login", json={"password": "wrong"})
    assert r.status_code == 429
    assert int(r.headers["Retry-After"]) > 0


def test_a_correct_password_is_refused_while_blocked(client):
    """Checking it would say which guess was right, which is the thing being prevented. The
    cost is yours: your own password does not work either, for at most five minutes."""
    wrong(client, 5)
    r = client.post("/api/login", json={"password": PASSWORD})
    assert r.status_code == 429
    assert "tartib_session" not in client.cookies


def test_the_door_opens_again(client, settings, monkeypatch):
    from datetime import timedelta

    from tartib import auth
    from tartib.clock import utcnow

    wrong(client, 5)
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 429
    monkeypatch.setattr(auth, "utcnow", lambda: utcnow() + timedelta(minutes=10))
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200


def test_a_success_clears_the_count(client, settings, monkeypatch):
    from datetime import timedelta

    from tartib import auth
    from tartib.clock import utcnow

    wrong(client, 5)
    monkeypatch.setattr(auth, "utcnow", lambda: utcnow() + timedelta(minutes=10))
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200
    # back to a clean slate: four more failures must still be free
    monkeypatch.undo()
    for _ in range(4):
        assert client.post("/api/login", json={"password": "wrong"}).status_code == 401


def test_the_bearer_path_is_throttled_too(client):
    """Rate limiting /api/login alone would be theatre: every route takes the same password as
    a bearer token, so guesses would simply move to one that is not watched."""
    for _ in range(4):
        r = client.get("/api/today", headers={"Authorization": "Bearer nope"})
        assert r.status_code == 401
    r = client.get("/api/today", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 429
    # and the correct bearer is refused during the block, for the same reason as the password
    good = client.get("/api/today", headers={"Authorization": f"Bearer {PASSWORD}"})
    assert good.status_code == 429


def test_failures_on_one_door_count_on_the_other(client):
    """One counter, because it is one password. Three guesses at the login and two at a bearer
    route is five guesses."""
    wrong(client, 3)
    assert client.get("/api/today", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.get("/api/today", headers={"Authorization": "Bearer nope"}).status_code == 429


def test_a_signed_in_browser_is_not_locked_out(client):
    """Someone hammering the door must not log you out of the tab you already have open."""
    assert client.post("/api/login", json={"password": PASSWORD}).status_code == 200
    wrong(client, 6)
    assert client.get("/api/today").status_code == 200


def test_the_count_survives_a_restart(settings):
    """In app_state, not in memory: a crash loop would otherwise be a free reset."""
    from fastapi.testclient import TestClient

    from tartib.main import create_app

    with TestClient(create_app(settings)) as first:
        wrong(first, 5)
    with TestClient(create_app(settings)) as second:
        assert second.post("/api/login", json={"password": PASSWORD}).status_code == 429


# `client` is here to build the app, which is what runs the migrations.
def test_the_window_grows_and_then_stops(client, settings):
    """Doubling from 30s, capped at five minutes, so a long attack cannot lock you out for an
    afternoon. Driven directly, because over HTTP a blocked attempt correctly records nothing:
    the window only grows once per window, which is the point."""
    from datetime import timedelta

    from tartib import auth, db
    from tartib.clock import utcnow

    conn = db.connect(settings.db_path)
    now = utcnow()
    windows = []
    try:
        for _ in range(12):
            auth.record_failure(conn, now)
            seconds = auth.blocked_seconds(conn, now)
            if seconds:
                windows.append(seconds)
                now += timedelta(seconds=seconds)  # wait it out, then guess again
    finally:
        conn.close()

    assert windows[0] == 30, windows
    assert windows[1] == 60, windows
    assert windows[2] == 120, windows
    assert max(windows) == 300, windows
    assert windows[-1] == 300, "it stops growing rather than climbing forever"
