"""The reminder loop: what it pushes, what it refuses to push, and what it writes down.

The clock is an argument, never `now()`, so every case here is exact.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime, timedelta

import pytest

from tartib import db, push
from tartib.main import create_app
from tartib.reminders import Reminders, mark_reminded
from tartib.vapid import generate
from tests.conftest import PASSWORD, capture, make_settings

# A real pair, generated per run: the startup check rejects anything that cannot sign.
TEST_PUBLIC, TEST_PRIVATE = generate()
VAPID = {
    "TARTIB_VAPID_PUBLIC": TEST_PUBLIC,
    "TARTIB_VAPID_PRIVATE": TEST_PRIVATE,
    "TARTIB_VAPID_EMAIL": "mailto:me@example.com",
    "TARTIB_TZ": "Asia/Karachi",  # UTC+5, so a UTC morning is a local morning
}
# A time no test reaches, for the cases that are not about the digest.
QUIET = {"TARTIB_SUMMARY_TIME": "23:59"}
MORNING = datetime(2026, 9, 17, 4, 0, tzinfo=UTC)  # 09:00 in Karachi


class FakeSender:
    """Stands in for the network. Raises whatever a test maps to an endpoint."""

    def __init__(self, raises: dict | None = None) -> None:
        self.sent: list[tuple[str, dict]] = []
        self.raises = raises or {}
        self.keys_used: set[str | None] = set()

    def __call__(self, row, payload, settings) -> None:
        # No assertions in here: broadcast() swallows exceptions, so a failed one would
        # surface as a confusing empty `sent` list. Record and let the test assert.
        self.keys_used.add(settings.vapid_private)
        error = self.raises.get(row["endpoint"])
        if error is not None:
            raise error
        self.sent.append((row["endpoint"], payload))

    @property
    def titles(self) -> list[str]:
        return [payload["title"] for _, payload in self.sent]


def loop(tmp_path, sender=None, **extra) -> tuple[Reminders, FakeSender]:
    """A reminder loop over the same database the client fixture writes to."""
    sender = sender or FakeSender()
    settings = make_settings(tmp_path, **VAPID, **extra)
    return Reminders(settings, sender=sender), sender


def subscribe(auth, endpoint: str = "https://push.example/a") -> str:
    r = auth.post(
        "/api/subscriptions",
        json={"endpoint": endpoint, "keys": {"p256dh": "key-material", "auth": "secret"}},
    )
    assert r.status_code == 201, r.text
    return endpoint


def task_with_reminder(auth, text: str, remind_at: str, title: str = "Call the bank") -> dict:
    """AI is off in these tests, so a capture waits in attention; approving files it."""
    item = capture(auth, text)["items"][0]
    r = auth.post(
        f"/api/items/{item['id']}/approve",
        json={"shape": "task", "space": "work", "title": title, "remind_at": remind_at},
    )
    assert r.status_code == 200, r.text
    return r.json()


def item_row(tmp_path, item_id: int) -> dict:
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        return dict(conn.execute("SELECT * FROM items WHERE id = ?", (item_id,)).fetchone())
    finally:
        conn.close()


def test_due_reminder_pushes_once(auth, tmp_path):
    task = task_with_reminder(auth, "call the bank at four", "2026-09-17T03:59:00Z")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)

    assert reminders.tick(MORNING) == {"reminded": 1, "expired": 0, "digest": False}
    assert sender.sent == [
        (
            "https://push.example/a",
            {"title": "Call the bank", "url": "/today", "tag": f"item-{task['id']}"},
        )
    ]
    assert sender.keys_used == {VAPID["TARTIB_VAPID_PRIVATE"]}
    assert item_row(tmp_path, task["id"])["reminded_at"] is not None

    # The moment has passed. A second tick must stay quiet.
    assert reminders.tick(MORNING + timedelta(minutes=1))["reminded"] == 0
    assert len(sender.sent) == 1


def test_reminder_is_not_yet_due(auth, tmp_path):
    task_with_reminder(auth, "call later", "2026-09-17T06:00:00Z")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)

    assert reminders.tick(MORNING)["reminded"] == 0
    assert sender.sent == []


def test_moving_the_reminder_rearms_it(auth, tmp_path):
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)
    reminders.tick(MORNING)
    assert len(sender.sent) == 1

    r = auth.patch(f"/api/items/{task['id']}", json={"remind_at": "2026-09-17T04:30:00Z"})
    assert r.status_code == 200, r.text
    assert item_row(tmp_path, task["id"])["reminded_at"] is None

    assert reminders.tick(datetime(2026, 9, 17, 4, 31, tzinfo=UTC))["reminded"] == 1
    assert len(sender.sent) == 2


def test_a_reminder_older_than_the_grace_window_is_dropped(auth, tmp_path):
    """The container was off overnight: the night is written off, not replayed."""
    task = task_with_reminder(auth, "call the bank", "2026-09-16T20:00:00Z")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)

    assert reminders.tick(MORNING) == {"reminded": 0, "expired": 1, "digest": False}
    assert sender.sent == []
    assert item_row(tmp_path, task["id"])["reminded_at"] is not None


def test_a_done_task_does_not_remind(auth, tmp_path):
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    assert auth.patch(f"/api/items/{task['id']}", json={"status": "done"}).status_code == 200
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)

    assert reminders.tick(MORNING)["reminded"] == 0
    assert sender.sent == []


def test_a_dead_subscription_is_deleted(auth, tmp_path):
    task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    dead = subscribe(auth, "https://push.example/dead")
    alive = subscribe(auth, "https://push.example/alive")
    sender = FakeSender(raises={dead: push.Gone("410")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)

    reminders.tick(MORNING)

    assert [endpoint for endpoint, _ in sender.sent] == [alive]
    assert auth.get("/api/subscriptions").json()["count"] == 1


def test_a_failing_push_still_marks_the_reminder_sent(auth, tmp_path):
    """A reminder is a moment, not a delivery guarantee. Retrying it next tick would nag."""
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    endpoint = subscribe(auth)
    sender = FakeSender(raises={endpoint: RuntimeError("push service down")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)

    assert reminders.tick(MORNING)["reminded"] == 1
    assert sender.sent == []
    assert item_row(tmp_path, task["id"])["reminded_at"] is not None
    assert auth.get("/api/subscriptions").json()["count"] == 1  # a failure is not a death


def test_a_fired_reminder_does_not_reset_the_stale_clock(auth, tmp_path):
    """`updated_at` is the human touch the stale list reads. A push is not a touch."""
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    subscribe(auth)
    before = item_row(tmp_path, task["id"])["updated_at"]

    reminders, _ = loop(tmp_path, **QUIET)
    reminders.tick(MORNING)

    assert item_row(tmp_path, task["id"])["updated_at"] == before


def test_editing_the_reminder_is_a_touch(auth, tmp_path):
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    before = item_row(tmp_path, task["id"])["updated_at"]

    auth.patch(f"/api/items/{task['id']}", json={"remind_at": "2026-09-18T04:30:00Z"})

    assert item_row(tmp_path, task["id"])["updated_at"] > before


def test_editing_the_title_does_not_fire_the_reminder_again(auth, tmp_path):
    """The editor resends `remind_at` on every save. Only a changed one may re-arm, or one
    title edit inside the grace window would push the same reminder a second time."""
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)
    reminders.tick(MORNING)
    assert len(sender.sent) == 1

    # Exactly what ItemEditor sends when only the title changed.
    r = auth.patch(
        f"/api/items/{task['id']}",
        json={
            "shape": "task",
            "space": "work",
            "title": "Call the bank now",
            "due": None,
            "remind_at": "2026-09-17T03:59:00Z",
        },
    )
    assert r.status_code == 200, r.text
    assert item_row(tmp_path, task["id"])["reminded_at"] is not None  # still spent

    assert reminders.tick(MORNING + timedelta(minutes=2))["reminded"] == 0
    assert len(sender.sent) == 1


def test_a_reminder_moved_mid_push_is_not_swallowed(auth, tmp_path):
    """Marking it sent is guarded on the `remind_at` the tick read, so a reminder moved while
    the push was in flight still fires at its new time."""
    task = task_with_reminder(auth, "call the bank", "2026-09-17T03:59:00Z")
    moved = "2026-09-17T04:30:00Z"
    auth.patch(f"/api/items/{task['id']}", json={"remind_at": moved})

    conn = db.connect(str(tmp_path / "t.db"))
    try:
        mark_reminded(conn, task["id"], "2026-09-17T03:59:00Z", "2026-09-17T04:00:00Z")
    finally:
        conn.close()
    assert item_row(tmp_path, task["id"])["reminded_at"] is None

    reminders, sender = loop(tmp_path, **QUIET)
    subscribe(auth)
    assert reminders.tick(datetime(2026, 9, 17, 4, 31, tzinfo=UTC))["reminded"] == 1


def test_an_undecided_item_is_not_written_off(auth, tmp_path):
    """Only a filed, open task is ever stamped. A proposal still in Needs Attention carries
    a proposed `remind_at` that was never armed, and approving it must still be able to fire."""
    cap = capture(auth, "call the bank")
    waiting = cap["items"][0]["id"]
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        conn.execute("UPDATE items SET remind_at = '2026-09-16T20:00:00Z' WHERE id = ?", (waiting,))
        conn.commit()
    finally:
        conn.close()

    reminders, _ = loop(tmp_path, **QUIET)
    assert reminders.tick(MORNING)["expired"] == 0
    assert item_row(tmp_path, waiting)["reminded_at"] is None


def test_two_reminders_in_one_tick_do_not_replace_each_other(auth, tmp_path):
    """A shared notification tag makes the second reminder swallow the first on the phone."""
    first = task_with_reminder(auth, "call the bank", "2026-09-17T03:58:00Z", title="Call the bank")
    second = task_with_reminder(auth, "pick up the parcel", "2026-09-17T03:59:00Z", title="Parcel")
    subscribe(auth)
    reminders, sender = loop(tmp_path, **QUIET)

    assert reminders.tick(MORNING)["reminded"] == 2
    tags = [payload["tag"] for _, payload in sender.sent]
    assert tags == [f"item-{first['id']}", f"item-{second['id']}"]
    assert len(set(tags)) == 2


# --- the daily digest ---


def test_digest_sends_once_a_day_across_a_restart(auth, tmp_path):
    task_with_reminder(auth, "file the taxes", "2026-09-20T04:00:00Z")
    capture(auth, "something to decide")  # waits: a bare POST may not be filed yet
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    # 08:01 in Karachi. The reminder itself is days away, so this is the digest alone.
    assert reminders.tick(datetime(2026, 9, 17, 3, 1, tzinfo=UTC))["digest"] is True
    assert sender.titles == ["0 due today, 1 need attention"]

    # A restart at 08:30 must neither repeat it nor skip tomorrow's.
    restarted, sender2 = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")
    assert restarted.tick(datetime(2026, 9, 17, 3, 30, tzinfo=UTC))["digest"] is False
    assert sender2.sent == []
    assert restarted.tick(datetime(2026, 9, 18, 3, 1, tzinfo=UTC))["digest"] is True
    assert len(sender2.sent) == 1


def test_a_first_start_after_the_digest_time_writes_that_day_off(auth, tmp_path):
    """Installing at 22:00 should not greet you with a digest. Tomorrow's still arrives."""
    capture(auth, "something to decide")
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    evening = datetime(2026, 9, 17, 17, 0, tzinfo=UTC)  # 22:00 in Karachi
    assert reminders.seed_digest(evening) is True
    assert reminders.tick(evening)["digest"] is False
    assert sender.sent == []

    assert reminders.tick(datetime(2026, 9, 18, 3, 1, tzinfo=UTC))["digest"] is True
    assert len(sender.sent) == 1


def test_a_first_start_before_the_digest_time_keeps_that_morning(auth, tmp_path):
    capture(auth, "something to decide")
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    assert reminders.seed_digest(datetime(2026, 9, 17, 2, 0, tzinfo=UTC)) is False  # 07:00
    assert reminders.tick(datetime(2026, 9, 17, 3, 1, tzinfo=UTC))["digest"] is True
    assert len(sender.sent) == 1


def test_digest_waits_for_the_configured_time(auth, tmp_path):
    capture(auth, "something to decide")
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    assert reminders.tick(datetime(2026, 9, 17, 2, 59, tzinfo=UTC))["digest"] is False
    assert sender.sent == []


def test_an_empty_day_sends_nothing_and_stays_quiet(auth, tmp_path):
    """Both counts zero: no push, and no digest later just because the day filled up."""
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    assert reminders.tick(datetime(2026, 9, 17, 3, 1, tzinfo=UTC))["digest"] is False
    assert sender.sent == []

    capture(auth, "a thing that arrived at noon")
    assert reminders.tick(datetime(2026, 9, 17, 7, 0, tzinfo=UTC))["digest"] is False
    assert sender.sent == []


def test_digest_counts_what_is_due_and_waiting(auth, tmp_path):
    item = capture(auth, "pay the bill")["items"][0]
    auth.post(
        f"/api/items/{item['id']}/approve",
        json={"shape": "task", "space": "work", "title": "Pay the bill", "due": "2026-09-17"},
    )
    capture(auth, "undecided one")
    capture(auth, "undecided two")
    subscribe(auth)
    reminders, sender = loop(tmp_path, TARTIB_SUMMARY_TIME="08:00")

    reminders.tick(datetime(2026, 9, 17, 3, 1, tzinfo=UTC))

    assert sender.titles == ["1 due today, 2 need attention"]


def failures(tmp_path, endpoint: str = "https://push.example/a") -> int | None:
    conn = db.connect(str(tmp_path / "t.db"))
    try:
        row = conn.execute(
            "SELECT failures FROM subscriptions WHERE endpoint = ?", (endpoint,)
        ).fetchone()
        return None if row is None else row["failures"]
    finally:
        conn.close()


def test_a_failing_endpoint_is_counted_out(auth, tmp_path):
    """A push service can have a bad minute. Eight bad minutes in a row is a dead device."""
    endpoint = subscribe(auth)
    sender = FakeSender(raises={endpoint: RuntimeError("push service down")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)

    for attempt in range(1, push.MAX_FAILURES):
        task = task_with_reminder(auth, f"call {attempt}", "2026-09-17T03:59:00Z")
        assert reminders.tick(MORNING)["reminded"] == 1, task
        assert failures(tmp_path) == attempt

    # the last straw
    task_with_reminder(auth, "the last one", "2026-09-17T03:59:00Z")
    reminders.tick(MORNING)
    assert failures(tmp_path) is None
    assert auth.get("/api/subscriptions").json()["count"] == 0


def test_one_delivery_clears_the_count(auth, tmp_path):
    endpoint = subscribe(auth)
    sender = FakeSender(raises={endpoint: RuntimeError("briefly unreachable")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)
    task_with_reminder(auth, "first", "2026-09-17T03:59:00Z")
    reminders.tick(MORNING)
    assert failures(tmp_path) == 1

    sender.raises = {}  # the push service comes back
    task_with_reminder(auth, "second", "2026-09-17T03:59:00Z")
    reminders.tick(MORNING)
    assert failures(tmp_path) == 0


def test_resubscribing_clears_the_count(auth, tmp_path):
    """The browser saying "here I am" is better evidence than the last failed push."""
    endpoint = subscribe(auth)
    sender = FakeSender(raises={endpoint: RuntimeError("down")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)
    task_with_reminder(auth, "first", "2026-09-17T03:59:00Z")
    reminders.tick(MORNING)
    assert failures(tmp_path) == 1

    subscribe(auth)
    assert failures(tmp_path) == 0


def test_a_dead_endpoint_still_goes_on_the_first_410(auth, tmp_path):
    """404 and 410 are the push service saying it is gone. That needs no second opinion."""
    endpoint = subscribe(auth)
    sender = FakeSender(raises={endpoint: push.Gone("410")})
    reminders, _ = loop(tmp_path, sender=sender, **QUIET)
    task_with_reminder(auth, "first", "2026-09-17T03:59:00Z")

    reminders.tick(MORNING)

    assert auth.get("/api/subscriptions").json()["count"] == 0


# --- wiring and transport ---


def test_the_loop_runs_only_when_keys_are_configured(tmp_path):
    from fastapi.testclient import TestClient

    with TestClient(create_app(make_settings(tmp_path))) as client:
        assert client.app.state.reminders is None
        assert (
            client.get("/api/config", headers={"Authorization": f"Bearer {PASSWORD}"}).json()[
                "vapid_public"
            ]
            is None
        )

    with TestClient(create_app(make_settings(tmp_path, **VAPID, **QUIET))) as client:
        assert client.app.state.reminders is not None
        config = client.get("/api/config", headers={"Authorization": f"Bearer {PASSWORD}"}).json()
        assert config["vapid_public"] == VAPID["TARTIB_VAPID_PUBLIC"]
        assert "vapid_private" not in config


def test_resubscribing_refreshes_the_row_instead_of_adding_one(auth):
    subscribe(auth)
    subscribe(auth)
    assert auth.get("/api/subscriptions").json()["count"] == 1

    r = auth.request("DELETE", "/api/subscriptions", json={"endpoint": "https://push.example/a"})
    assert r.json() == {"ok": True, "removed": 1}
    assert auth.get("/api/subscriptions").json()["count"] == 0


def test_subscriptions_need_auth(client):
    assert client.get("/api/subscriptions").status_code == 401


@pytest.mark.parametrize("status,gone", [(404, True), (410, True), (500, False)])
def test_send_maps_a_dead_endpoint_to_gone(monkeypatch, tmp_path, status, gone):
    """The one bit of the real transport worth pinning: which failures kill a subscription."""
    import pywebpush

    class Response:
        status_code = status

    def explode(**kwargs):
        raise pywebpush.WebPushException("no", response=Response())

    monkeypatch.setattr(pywebpush, "webpush", explode)
    row = {"endpoint": "https://push.example/a", "p256dh": "k", "auth": "s"}
    settings = make_settings(tmp_path, **VAPID)

    with pytest.raises(push.Gone if gone else pywebpush.WebPushException):
        push.send(row, {"title": "x", "url": "/today"}, settings)


def test_the_running_app_pushes_without_anyone_calling_tick(auth, tmp_path, monkeypatch):
    """The loop is wired to startup: no test drives it here, the app does."""
    from fastapi.testclient import TestClient

    # The live loop reads the real clock, so the reminder is anchored to real time.
    just_now = (datetime.now(UTC) - timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    task = task_with_reminder(auth, "call the bank", just_now)
    subscribe(auth)
    sent: list[dict] = []
    monkeypatch.setattr(push, "send", lambda row, payload, settings: sent.append(payload))

    with TestClient(create_app(make_settings(tmp_path, **VAPID, **QUIET))) as client:
        assert client.app.state.reminders is not None
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline and not sent:
            time.sleep(0.02)

    assert sent == [{"title": "Call the bank", "url": "/today", "tag": f"item-{task['id']}"}]
    assert item_row(tmp_path, task["id"])["reminded_at"] is not None


def test_a_generated_key_pair_actually_signs_a_push():
    """The key format in .env.example is the one pywebpush accepts. Nothing leaves the
    machine: a stand-in session captures the request that would have been sent."""
    from pywebpush import webpush

    from tartib.vapid import b64

    sent = {}

    class Session:
        def post(self, endpoint, data=None, headers=None, timeout=None, **kwargs):
            sent.update(endpoint=endpoint, data=data, headers=dict(headers or {}))

            class Response:
                status_code = 201
                text = ""
                headers: dict = {}

            return Response()

    public, private = generate()
    webpush(
        subscription_info={
            "endpoint": "https://push.example/a",
            "keys": {"p256dh": public, "auth": b64(b"0123456789abcdef")},
        },
        data='{"title": "Call the bank", "url": "/today"}',
        vapid_private_key=private,
        vapid_claims={"sub": "mailto:me@example.com"},
        requests_session=Session(),
    )

    auth_header = sent["headers"]["authorization"]
    assert auth_header.startswith("vapid t=")
    assert f"k={public}" in auth_header  # the key the browser subscribed with
    assert private not in str(sent)  # the private key signs; it is never transmitted
    assert b"Call the bank" not in sent["data"]  # the payload goes out encrypted


def test_an_unusable_private_key_turns_the_loop_off(tmp_path, caplog):
    """Better no reminders than reminders marked sent that nobody could receive."""
    from fastapi.testclient import TestClient

    broken = dict(VAPID, TARTIB_VAPID_PRIVATE="not-a-key")
    with caplog.at_level("ERROR"):
        with TestClient(create_app(make_settings(tmp_path, **broken, **QUIET))) as client:
            assert client.app.state.reminders is None
    assert "unusable" in caplog.text
    assert "not-a-key" not in caplog.text  # never log the key itself


def test_a_generated_key_passes_the_startup_check(tmp_path):
    public, private = generate()
    settings = make_settings(
        tmp_path,
        TARTIB_VAPID_PUBLIC=public,
        TARTIB_VAPID_PRIVATE=private,
        TARTIB_VAPID_EMAIL="mailto:me@example.com",
    )
    push.check_key(settings)  # raises if the pair the generator prints is not usable
