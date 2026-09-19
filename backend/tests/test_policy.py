"""A filing policy per space: the global threshold, always ask, or always file."""

from __future__ import annotations

import pytest

from tartib.store import should_file
from tests.conftest import capture, proposal, set_classify_reply


@pytest.mark.parametrize(
    "policy, confidence, expected",
    [
        ("auto", 0.95, True),
        ("auto", 0.60, False),
        ("ask", 0.99, False),
        ("file", 0.10, True),
    ],
)
def test_the_rule(policy, confidence, expected):
    assert should_file("work", confidence, 0.85, {"work": policy}) is expected


def test_no_space_never_files_whatever_the_policy():
    assert should_file(None, 0.99, 0.85, {"work": "file"}) is False


def stage_of(ai_client, monkeypatch, conf):
    set_classify_reply(monkeypatch, proposal(space="work", confidence=conf))
    return capture(ai_client, "a thing for work")["items"][0]["stage"]


def test_the_runner_follows_the_space(ai_client, monkeypatch):
    assert stage_of(ai_client, monkeypatch, 0.95) == "filed"  # auto
    assert stage_of(ai_client, monkeypatch, 0.60) == "attention"

    assert ai_client.put("/api/spaces/work/policy", json={"policy": "ask"}).status_code == 200
    assert stage_of(ai_client, monkeypatch, 0.99) == "attention"

    ai_client.put("/api/spaces/work/policy", json={"policy": "file"})
    assert stage_of(ai_client, monkeypatch, 0.20) == "filed"


def test_policies_are_listed_set_and_kept_across_a_rename(auth):
    assert auth.get("/api/spaces").json()["policies"]["home"] == "auto"
    assert auth.put("/api/spaces/home/policy", json={"policy": "ask"}).json() == {
        "name": "home",
        "policy": "ask",
    }
    auth.patch("/api/spaces/home", json={"name": "house"})
    assert auth.get("/api/spaces").json()["policies"]["house"] == "ask"
    assert auth.put("/api/spaces/nowhere/policy", json={"policy": "ask"}).status_code == 404
    assert auth.put("/api/spaces/house/policy", json={"policy": "sometimes"}).status_code == 422
