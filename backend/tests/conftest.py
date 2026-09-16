from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from tartib.config import load_settings
from tartib.main import create_app

PASSWORD = "hunter2"


def make_settings(tmp_path, **extra):
    env = {"TARTIB_PASSWORD": PASSWORD, "TARTIB_DB_PATH": str(tmp_path / "t.db")}
    env.update(extra)
    return load_settings(env)


@pytest.fixture
def settings(tmp_path):
    return make_settings(tmp_path)


@pytest.fixture
def client(settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as c:
        yield c


@pytest.fixture
def auth(client) -> TestClient:
    client.headers["Authorization"] = f"Bearer {PASSWORD}"
    return client
