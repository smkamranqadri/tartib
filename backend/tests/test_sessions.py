"""Pomodoro sessions: the row, the outcome, and the push at the end.

The scheduler's clock is an argument, never `now()`, so every case here is exact.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from tartib import db
from tartib.sessions import PUSH_GRACE, Sessions, counts_today, space_counts_today
from tests.conftest import capture, make_settings
from tests.test_reminders import QUIET, VAPID, FakeSender, subscribe

NOW = datetime(2026, 9, 18, 4, 0, tzinfo=UTC)  # 09:00 in Karachi


def clock(tmp_path, sender=None, **extra) -> tuple[Sessions, FakeSender]:
    sender = sender or FakeSender()
    settings = make_settings(tmp_path, **VAPID, **QUIET, **extra)
    return Sessions(settings, sender=sender), sender


def a_task(auth, text="prune the disk", title="Prune disk usage", space="work") -> dict:
    item = capture(auth, text)["items"][0]
    r = auth.post(
        f"/api/items/{item['id']}/approve",
        json={"shape": "task", "space": space, "title": title},
    )
    assert r.status_code == 200, r.text
    return r.json()


def row(tmp_path, session_id: int) -> dict:
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        return dict(conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone())
    finally:
        conn.close()


def test_a_session_can_be_about_a_task_or_about_nothing(auth):
    task = a_task(auth)
    on_task = auth.post("/api/sessions", json={"item_id": task["id"]})
    assert on_task.status_code == 201, on_task.text
    assert on_task.json()["item_id"] == task["id"]

    auth.post(f"/api/sessions/{on_task.json()['id']}/stop")
    bare = auth.post("/api/sessions", json={})
    assert bare.status_code == 201
    assert bare.json()["item_id"] is None


def test_only_one_runs_at_a_time(auth):
    first = auth.post("/api/sessions", json={}).json()
    second = auth.post("/api/sessions", json={})
    assert second.status_code == 409
    assert "already running" in second.json()["detail"]

    # but a session still owed an outcome must not stop the next one
    auth.post(f"/api/sessions/{first['id']}/stop")
    assert auth.post("/api/sessions", json={}).status_code == 201


def test_current_survives_a_closed_tab(auth):
    task = a_task(auth)
    started = auth.post("/api/sessions", json={"item_id": task["id"]}).json()

    now = auth.get("/api/sessions/current").json()
    assert now["state"] == "running"
    assert now["session"]["id"] == started["id"]
    assert now["item"]["title"] == "Prune disk usage"


def test_a_session_that_ended_while_you_were_away_is_waiting(auth, tmp_path):
    started = auth.post("/api/sessions", json={}).json()
    # wind it back so its time is up
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        conn.execute(
            "UPDATE sessions SET started_at = '2026-09-18T03:00:00Z', ends_at ="
            " '2026-09-18T03:25:00Z' WHERE id = ?",
            (started["id"],),
        )
        conn.commit()
    finally:
        conn.close()

    current = auth.get("/api/sessions/current").json()
    assert current["state"] == "awaiting"
    assert current["session"]["id"] == started["id"]
    assert row(tmp_path, started["id"])["ended_at"] is not None  # tidied on the way past


def test_a_session_from_yesterday_stops_asking(auth, tmp_path):
    """An outcome sheet for something from two days ago is an ambush, not a question."""
    stale = auth.post("/api/sessions", json={}).json()
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        long_ago = datetime.now(UTC) - timedelta(hours=13)
        conn.execute(
            "UPDATE sessions SET started_at = ?, ends_at = ? WHERE id = ?",
            (
                (long_ago - timedelta(minutes=25)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                long_ago.strftime("%Y-%m-%dT%H:%M:%SZ"),
                stale["id"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    current = auth.get("/api/sessions/current").json()
    assert current["state"] is None, current
    assert auth.post("/api/sessions", json={}).status_code == 201  # and it blocks nothing


def test_done_ticks_the_task_off(auth):
    task = a_task(auth)
    session = auth.post("/api/sessions", json={"item_id": task["id"]}).json()

    r = auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "done"})
    assert r.status_code == 200, r.text
    assert r.json()["outcome"] == "done"
    assert auth.get(f"/api/items/{task['id']}").json()["status"] == "done"


def test_the_other_two_outcomes_leave_the_task_open(auth):
    for outcome in ("unfinished", "abandoned"):
        task = a_task(auth)
        session = auth.post("/api/sessions", json={"item_id": task["id"]}).json()
        auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": outcome})
        assert auth.get(f"/api/items/{task['id']}").json()["status"] == "open"


def test_an_outcome_is_answered_once(auth):
    session = auth.post("/api/sessions", json={}).json()
    auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "abandoned"})
    again = auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "done"})
    assert again.status_code == 409


def test_a_session_with_no_task_can_still_be_done(auth):
    session = auth.post("/api/sessions", json={}).json()
    r = auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "done"})
    assert r.status_code == 200
    assert r.json()["outcome"] == "done"


# --- the push at the end ---


def test_the_end_pushes_once(auth, tmp_path):
    task = a_task(auth)
    subscribe(auth)
    session = auth.post("/api/sessions", json={"item_id": task["id"]}).json()
    sessions, sender = clock(tmp_path)

    ends = datetime.fromisoformat(session["ends_at"].replace("Z", "+00:00"))
    assert sessions.fire(session["id"], ends) is True
    assert sender.titles == ["Session done: Prune disk usage"]
    assert sender.sent[0][1]["tag"] == f"session-{session['id']}"
    assert row(tmp_path, session["id"])["ended_at"] is not None

    # and never twice
    assert sessions.fire(session["id"], ends) is False
    assert len(sender.sent) == 1


def test_a_session_stopped_by_hand_does_not_buzz(auth, tmp_path):
    subscribe(auth)
    session = auth.post("/api/sessions", json={}).json()
    auth.post(f"/api/sessions/{session['id']}/stop")
    sessions, sender = clock(tmp_path)

    ends = datetime.fromisoformat(session["ends_at"].replace("Z", "+00:00"))
    assert sessions.fire(session["id"], ends) is False
    assert sender.sent == []


def test_a_session_that_ended_while_the_container_was_down_does_not_buzz(auth, tmp_path):
    subscribe(auth)
    session = auth.post("/api/sessions", json={}).json()
    sessions, sender = clock(tmp_path)

    ends = datetime.fromisoformat(session["ends_at"].replace("Z", "+00:00"))
    assert sessions.fire(session["id"], ends + PUSH_GRACE + timedelta(seconds=1)) is False
    assert sender.sent == []
    assert row(tmp_path, session["id"])["ended_at"] is not None  # still closed out


def test_a_session_with_no_task_says_so(auth, tmp_path):
    subscribe(auth)
    session = auth.post("/api/sessions", json={}).json()
    sessions, sender = clock(tmp_path)

    ends = datetime.fromisoformat(session["ends_at"].replace("Z", "+00:00"))
    sessions.fire(session["id"], ends)
    assert sender.titles == ["Session done"]


def test_an_answered_session_does_not_buzz(auth, tmp_path):
    subscribe(auth)
    session = auth.post("/api/sessions", json={}).json()
    auth.post(f"/api/sessions/{session['id']}/outcome", json={"outcome": "done"})
    sessions, sender = clock(tmp_path)

    ends = datetime.fromisoformat(session["ends_at"].replace("Z", "+00:00"))
    assert sessions.fire(session["id"], ends) is False
    assert sender.sent == []


# --- counts ---


def test_today_counts_the_total_and_the_task(auth, tmp_path):
    task = a_task(auth)
    first = auth.post("/api/sessions", json={"item_id": task["id"]}).json()
    auth.post(f"/api/sessions/{first['id']}/outcome", json={"outcome": "unfinished"})
    second = auth.post("/api/sessions", json={}).json()
    auth.post(f"/api/sessions/{second['id']}/stop")

    counts = auth.get("/api/today").json()["sessions"]
    assert counts["total"] == 2
    assert counts["by_item"] == {str(task["id"]): 1}


def test_a_session_with_no_task_belongs_to_no_space(auth, tmp_path):
    task = a_task(auth)
    auth.post("/api/sessions", json={"item_id": task["id"]})
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        settings = make_settings(tmp_path)
        assert space_counts_today(conn, settings, NOW) == {"work": 1}
        assert counts_today(conn, settings, NOW)["total"] == 1
    finally:
        conn.close()


def test_the_running_app_ends_a_session_by_itself(auth, tmp_path, monkeypatch):
    """No test drives the clock here: the app schedules the end and fires it."""
    import time

    from fastapi.testclient import TestClient

    from tartib import push
    from tartib.main import create_app
    from tests.conftest import PASSWORD

    sent: list[dict] = []
    monkeypatch.setattr(push, "send", lambda row, payload, settings: sent.append(payload))
    subscribe(auth)

    # a one-second session, so the scheduler has something to wait for
    settings = make_settings(tmp_path, **VAPID, **QUIET, TARTIB_SESSION_MINUTES="1")
    with TestClient(create_app(settings)) as client:
        client.headers["Authorization"] = f"Bearer {PASSWORD}"
        session = client.post("/api/sessions", json={}).json()
        conn = db.connect(str(tmp_path / "t.db"))
        try:  # bring its end forward rather than waiting a minute
            conn.execute(
                "UPDATE sessions SET ends_at = ? WHERE id = ?",
                (
                    (datetime.now(UTC) + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    session["id"],
                ),
            )
            conn.commit()
        finally:
            conn.close()
        client.app.state.sessions.arm(
            session["id"], (datetime.now(UTC) + timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        )

        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not sent:
            time.sleep(0.05)

    assert sent and sent[0]["title"] == "Session done", sent
    assert row(tmp_path, session["id"])["ended_at"] is not None
