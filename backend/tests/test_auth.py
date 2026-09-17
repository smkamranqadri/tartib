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
