"""Spaces as data: seed, create, rename, delete, and what the classifier sees."""

import json

from fastapi.testclient import TestClient

from tartib.main import create_app
from tests.conftest import PASSWORD, capture, make_settings, proposal, records, set_classify_reply


def test_seeded_from_env_once(tmp_path):
    settings = make_settings(tmp_path, TARTIB_SPACES="alpha,beta")
    with TestClient(create_app(settings)) as c:
        c.headers["Authorization"] = f"Bearer {PASSWORD}"
        assert c.get("/api/spaces").json()["spaces"] == ["alpha", "beta"]
        c.post("/api/spaces", json={"name": "gamma"})
    # env changes later are ignored: the table is the truth now
    with TestClient(create_app(make_settings(tmp_path, TARTIB_SPACES="zeta"))) as c:
        c.headers["Authorization"] = f"Bearer {PASSWORD}"
        assert c.get("/api/spaces").json()["spaces"] == ["alpha", "beta", "gamma"]


def test_no_env_means_no_spaces_until_created(tmp_path):
    with TestClient(create_app(make_settings(tmp_path, TARTIB_SPACES=""))) as c:
        c.headers["Authorization"] = f"Bearer {PASSWORD}"
        assert c.get("/api/spaces").json()["spaces"] == []
        assert c.post("/api/spaces", json={"name": " Gym "}).status_code == 201
        assert c.get("/api/spaces").json()["spaces"] == ["gym"]


def test_create_validation(auth):
    for bad in ["", "   ", "has space", "UPPER-only?", "x" * 25, "-lead"]:
        assert auth.post("/api/spaces", json={"name": bad}).status_code in (409, 422), bad
    assert auth.post("/api/spaces", json={"name": "work"}).status_code == 409
    r = auth.post("/api/spaces", json={"name": "Side-Projects"})
    assert r.status_code == 201 and r.json()["name"] == "side-projects"
    assert "side-projects" in auth.get("/api/config").json()["spaces"]


def test_rename_carries_items_and_brief(ai_client, monkeypatch):
    set_classify_reply(monkeypatch, proposal(shape="note", text="x", space="work"))
    item = capture(ai_client, "x")["items"][0]
    monkeypatch.setenv(
        "FAKE_CODEX_REPLY_ASK", json.dumps({"answer": "brief", "item_ids": [item["id"]]})
    )
    assert ai_client.get("/api/spaces/work/brief").json()["fresh"] is True
    r = ai_client.patch("/api/spaces/work", json={"name": "office"})
    assert (
        r.status_code == 200 and "office" in r.json()["spaces"] and "work" not in r.json()["spaces"]
    )
    assert ai_client.get(f"/api/items/{item['id']}").json()["space"] == "office"
    assert ai_client.get("/api/spaces/office/brief").json()["fresh"] is False  # cache moved too
    assert ai_client.get("/api/spaces/work/brief").status_code == 404
    assert ai_client.patch("/api/spaces/office", json={"name": "home"}).status_code == 409
    assert ai_client.patch("/api/spaces/nope", json={"name": "x"}).status_code == 404
    assert ai_client.patch(f"/api/items/{item['id']}", json={"space": "work"}).status_code == 422


def test_delete_only_when_empty(auth):
    item = capture(auth, "x")["items"][0]
    auth.post(f"/api/items/{item['id']}/approve", json={"space": "travel"})
    r = auth.delete("/api/spaces/travel")
    assert r.status_code == 409 and "1 item" in r.json()["detail"]
    auth.patch(f"/api/items/{item['id']}", json={"space": "home"})
    assert auth.delete("/api/spaces/travel").status_code == 200
    assert "travel" not in auth.get("/api/spaces").json()["spaces"]
    assert auth.delete("/api/spaces/travel").status_code == 404
    assert auth.post(f"/api/items/{item['id']}/approve").status_code == 409  # already filed


def test_classifier_sees_created_space(ai_client, monkeypatch, tmp_path):
    record = tmp_path / "calls.jsonl"
    ai_client.post("/api/spaces", json={"name": "gym"})
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(
        monkeypatch, proposal(shape="task", text="bench", space="gym", title="Bench")
    )
    item = capture(ai_client, "bench")["items"][0]
    assert item["space"] == "gym" and item["stage"] == "filed"
    assert (
        "Existing spaces: work, home, health, finance, ideas, travel, gym"
        in records(record)[-1]["argv"][-1]
    )
