"""Slice 29: what the AI costs -- the event stream, the row, the prices, the readout."""

from __future__ import annotations

import json

import pytest

from tartib import db
from tartib.codex import Usage, parse_events
from tartib.store import failure_reason, record_call, usage_for_capture, usage_totals
from tartib.usage import SHIPPED, UNKNOWN, Rates, rates_for
from tests.conftest import capture, proposal, set_classify_reply

# --- the event stream ---


def test_usage_is_read_off_turn_completed():
    stream = b"\n".join(
        [
            json.dumps({"type": "thread.started", "thread_id": "x"}).encode(),
            json.dumps({"type": "turn.started"}).encode(),
            json.dumps(
                {
                    "type": "turn.completed",
                    "usage": {
                        "input_tokens": 1200,
                        "cached_input_tokens": 400,
                        "cache_write_input_tokens": 100,
                        "output_tokens": 90,
                        "reasoning_output_tokens": 30,
                        "total_tokens": 1390,
                    },
                }
            ).encode(),
        ]
    )
    usage, message = parse_events(stream)
    assert usage.input_tokens == 1200 and usage.total_tokens == 1390
    assert usage.reasoning_output_tokens == 30
    assert message is None


def test_the_error_message_survives_the_json_stream():
    """The regression this slice had to avoid: before --json, CodexError took the last line of
    stdout. With the stream on, that line is a JSON blob."""
    text = "You've hit your usage limit. ... or try again at 11:46 AM."
    stream = b"\n".join(
        [
            json.dumps({"type": "turn.started"}).encode(),
            json.dumps({"type": "error", "message": text}).encode(),
            json.dumps({"type": "turn.failed", "error": {"message": text}}).encode(),
        ]
    )
    usage, message = parse_events(stream)
    assert message == text
    assert usage.empty


def test_a_turn_with_no_usage_reports_empty_rather_than_guessing():
    usage, _ = parse_events(json.dumps({"type": "turn.completed"}).encode())
    assert usage.empty and usage.total_tokens == 0


def test_garbage_on_stdout_is_ignored():
    usage, message = parse_events(b"not json\n\n{broken\n")
    assert usage.empty and message is None


# --- what is billable ---


def test_reasoning_tokens_are_not_billed_twice():
    """They are reported separately but already counted inside output_tokens."""
    usage = Usage(
        input_tokens=1000,
        cached_input_tokens=400,
        cache_write_input_tokens=100,
        output_tokens=90,
        reasoning_output_tokens=30,
        total_tokens=1190,
    )
    fresh, cached, written, output = usage.billable()
    assert fresh == 600  # input minus the part that came from cache
    assert cached == 400 and written == 100
    assert output == 90  # not 120


def test_cost_uses_each_rate_on_its_own_tokens():
    rates = Rates(input=0.20, output=1.20, cache_read=0.02, cache_write=0.25)
    usage = Usage(
        input_tokens=1_000_000,
        cached_input_tokens=0,
        cache_write_input_tokens=0,
        output_tokens=1_000_000,
        total_tokens=2_000_000,
    )
    assert rates.cost(usage) == pytest.approx(1.40)  # 0.20 in + 1.20 out


# --- failures ---


@pytest.mark.parametrize(
    "message, reason, resets",
    [
        (
            "exit 1: You've hit your usage limit. ... try again at 11:46 AM.",
            "usage_limit",
            "11:46 AM",
        ),
        ("You've hit your usage limit.", "usage_limit", None),
        ("timed out after 120s", "timeout", None),
        ("exit 3: something else", "other", None),
    ],
)
def test_the_usage_limit_is_its_own_kind_of_failure(message, reason, resets):
    assert failure_reason(message) == (reason, resets)


# --- the row ---


def _conn(settings):
    conn = db.connect(settings.db_path)
    db.migrate(conn)
    return conn


def test_a_call_is_recorded_with_its_counts(settings):
    conn = _conn(settings)
    record_call(
        conn,
        kind="classify",
        model="gpt-5.6-luna",
        usage=Usage(input_tokens=1200, output_tokens=90, total_tokens=1290),
        capture_id=7,
        duration_ms=8400,
    )
    totals = usage_totals(conn)
    assert totals["calls"] == 1 and totals["failed"] == 0
    assert totals["input_tokens"] == 1200 and totals["duration_ms"] == 8400
    assert usage_for_capture(conn, 7)["total_tokens"] == 1290
    assert usage_for_capture(conn, 999) is None  # nothing recorded, and says so
    conn.close()


def test_a_failed_call_keeps_the_clis_own_words(settings):
    conn = _conn(settings)
    record_call(
        conn,
        kind="classify",
        model="gpt-5.6-luna",
        usage=None,
        duration_ms=400,
        failure="exit 1: You've hit your usage limit. ... try again at 11:46 AM.",
    )
    totals = usage_totals(conn)
    assert totals["calls"] == 1 and totals["failed"] == 1
    assert totals["total_tokens"] == 0  # quota spent, nothing reported
    assert totals["usage_limit"]["count"] == 1
    assert totals["usage_limit"]["resets_at"] == "11:46 AM"
    conn.close()


def test_recording_never_raises_even_with_no_table(settings):
    """A bookkeeping failure must not cost a capture."""
    conn = db.connect(settings.db_path)  # migrations deliberately not run
    record_call(conn, kind="classify", model=None, usage=Usage(), duration_ms=1)
    conn.close()


# --- prices ---


def test_rates_fall_back_to_the_shipped_numbers(tmp_path):
    rates = rates_for("gpt-5.6-luna", str(tmp_path / "t.db"))
    assert rates.source == "shipped" and rates == SHIPPED["gpt-5.6-luna"]


def test_an_unknown_model_costs_nothing_rather_than_guessing(tmp_path):
    assert rates_for("some-model-nobody-priced", str(tmp_path / "t.db")) == UNKNOWN
    assert rates_for(None, str(tmp_path / "t.db")) == UNKNOWN


def test_a_cached_price_wins_over_the_shipped_one(tmp_path):
    (tmp_path / "ai-prices.json").write_text(
        json.dumps(
            {"gpt-5.6-luna": {"input": 9.0, "output": 9.0, "cache_read": 9.0, "cache_write": 9.0}}
        )
    )
    rates = rates_for("gpt-5.6-luna", str(tmp_path / "t.db"))
    assert rates.source == "cached" and rates.input == 9.0


def test_a_corrupt_cache_falls_back_rather_than_failing(tmp_path):
    (tmp_path / "ai-prices.json").write_text("{not json")
    assert rates_for("gpt-5.6-luna", str(tmp_path / "t.db")).source == "shipped"


# --- end to end through the fake CLI ---


def test_a_real_capture_records_its_call(ai_client, monkeypatch):
    set_classify_reply(monkeypatch, proposal(shape="note", text="x", space="work"))
    cap = capture(ai_client, "something to file")

    body = ai_client.get("/api/usage").json()
    assert body["calls"] >= 1 and body["failed"] == 0
    assert body["total_tokens"] > 0  # the fake reports a usage object
    assert body["model"] == body["model"]  # present, whatever it is in tests
    assert body["captures"] >= 1
    assert body["rates"]["source"] in ("shipped", "cached", "fetched", "unknown")
    assert cap["status"] == "done"


def test_a_failing_capture_records_the_failure(ai_client, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_EXIT", "1")
    monkeypatch.setenv(
        "FAKE_CODEX_ERROR", "You've hit your usage limit. ... try again at 11:46 AM."
    )
    capture(ai_client, "this one fails")

    body = ai_client.get("/api/usage").json()
    assert body["failed"] >= 1
    assert body["usage_limit"]["count"] >= 1
    assert body["usage_limit"]["resets_at"] == "11:46 AM"


def test_a_turn_without_usage_records_a_row_with_no_tokens(ai_client, monkeypatch):
    monkeypatch.setenv("FAKE_CODEX_NO_USAGE", "1")
    set_classify_reply(monkeypatch, proposal(shape="note", text="x", space="work"))
    capture(ai_client, "no usage reported")

    body = ai_client.get("/api/usage").json()
    assert body["calls"] >= 1 and body["total_tokens"] == 0
