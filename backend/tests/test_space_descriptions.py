from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from tartib import db
from tartib.classify import (
    DESCRIPTION_BUDGET,
    SPACE_CONTEXT_BUDGET,
    build_prompt,
    render_descriptions,
    render_space_context,
)
from tartib.space_descriptions import (
    DescriptionError,
    StaleDescription,
    normalize_description,
    set_space_description,
)
from tartib.store import SpaceContext, classify_context
from tests.conftest import capture, proposal, records, set_classify_reply


def test_validation_counts_unicode_codepoints_and_normalizes_lines():
    assert normalize_description("  one\r\ntwo  ") == "one\ntwo"
    assert normalize_description("🙂" * 500) == "🙂" * 500
    for bad in ("🙂" * 501, "a\x00b", "a\tb"):
        with pytest.raises(DescriptionError):
            normalize_description(bad)


def test_migration_adds_blank_fields_without_changing_existing_space_rows(tmp_path):
    conn = db.connect(str(tmp_path / "migration.db"))
    try:
        assert db.migrate(conn, up_to=24) == 24
        conn.execute("INSERT INTO spaces(name, position, created_at) VALUES ('work', 0, 'then')")
        conn.commit()
        assert db.migrate(conn) == 25
        row = conn.execute(
            "SELECT description, description_updated_at FROM spaces WHERE name='work'"
        ).fetchone()
        assert tuple(row) == ("", "")
    finally:
        conn.close()


def test_rest_read_write_clear_validation_and_token_advance(auth):
    initial = auth.get("/api/spaces").json()
    assert initial["spaces"] == ["work", "home", "health", "finance", "ideas", "travel"]
    assert all(
        d["description"] == "" and d["updated_at"] == "" for d in initial["descriptions"].values()
    )
    url = "/api/spaces/work/description"
    body = {"description": "  school\r\nfollow-ups  ", "updated_at": ""}
    first = auth.put(url, json=body)
    assert first.status_code == 200
    saved = first.json()
    assert saved["description"] == "school\nfollow-ups"
    same = auth.put(
        url, json={"description": saved["description"], "updated_at": saved["updated_at"]}
    )
    assert same.status_code == 200 and same.json()["updated_at"] > saved["updated_at"]
    stale = auth.put(url, json={"description": "lost", "updated_at": saved["updated_at"]})
    assert stale.status_code == 409
    cleared = auth.put(url, json={"description": "  ", "updated_at": same.json()["updated_at"]})
    assert cleared.status_code == 200 and cleared.json()["description"] == ""
    assert cleared.json()["updated_at"] > same.json()["updated_at"]
    assert (
        auth.put(
            url, json={"description": "x" * 501, "updated_at": cleared.json()["updated_at"]}
        ).status_code
        == 422
    )
    assert (
        auth.put(
            "/api/spaces/nope/description", json={"description": "x", "updated_at": ""}
        ).status_code
        == 404
    )


def test_description_rename_carries_and_delete_removes(auth):
    saved = auth.put(
        "/api/spaces/travel/description", json={"description": "Trips", "updated_at": ""}
    ).json()
    assert auth.patch("/api/spaces/travel", json={"name": "journeys"}).status_code == 200
    assert auth.get("/api/spaces").json()["descriptions"]["journeys"]["description"] == "Trips"
    assert auth.delete("/api/spaces/journeys").status_code == 200
    assert "journeys" not in auth.get("/api/spaces").json()["descriptions"]
    assert saved["updated_at"]


def test_concurrent_same_token_has_one_winner(tmp_path):
    path = str(tmp_path / "cas.db")
    conn = db.connect(path)
    db.migrate(conn)
    conn.execute("INSERT INTO spaces(name, position, created_at) VALUES ('work',0,'now')")
    conn.commit()
    conn.close()

    def write(text):
        c = db.connect(path)
        try:
            return set_space_description(c, "work", text, "")
        finally:
            c.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(write, text) for text in ("one", "two")]
        outcomes = []
        for future in futures:
            try:
                outcomes.append(future.result())
            except StaleDescription:
                outcomes.append("stale")
    assert sum(isinstance(o, dict) for o in outcomes) == 1
    assert outcomes.count("stale") == 1


def test_classifier_description_rendering_is_quoted_fair_and_hard_bounded():
    spaces = tuple(
        SpaceContext(f"s{i}", 1, 2, ("recent item",), description=('purpose 🙂\n" ' + "x" * 500))
        for i in range(20)
    )
    descriptions, existing = render_space_context(spaces)
    assert len(descriptions) <= DESCRIPTION_BUDGET
    assert len(descriptions) + len(existing) <= SPACE_CONTEXT_BUDGET
    assert "untrusted text" in descriptions
    assert "\\n" in descriptions and '\\"' in descriptions
    assert "[truncated]" in descriptions
    prompt = build_prompt("test", make_context(spaces))
    assert descriptions in prompt and existing in prompt
    assert len(descriptions) + len(existing) <= 12_000


def test_33_full_descriptions_keep_every_name_and_enforce_wrapped_caps():
    spaces = tuple(
        SpaceContext(
            f"space-{i:02}", 10_000 + i, 500 + i, (), description=f"Purpose {i}: " + "x" * 485
        )
        for i in range(33)
    )
    descriptions, existing = render_space_context(spaces)
    assert len(descriptions) <= DESCRIPTION_BUDGET
    assert len(existing) <= 4_000
    assert len(descriptions) + len(existing) <= SPACE_CONTEXT_BUDGET
    assert all(f"- space-{i:02}:" in descriptions for i in range(33))
    assert "[truncated]" in descriptions
    assert render_space_context(spaces) == (descriptions, existing)


def make_context(spaces):
    from datetime import UTC, datetime
    from zoneinfo import ZoneInfo

    from tartib.classify import Context
    from tartib.codex import CodexConfig

    return Context(
        datetime.now(UTC),
        ZoneInfo("UTC"),
        [s.name for s in spaces],
        CodexConfig("off"),
        existing=spaces,
    )


def test_empty_descriptions_keep_baseline_prompt_without_new_block():
    spaces = (SpaceContext("work", 2, 1, ("a task",)),)
    assert render_descriptions(spaces) == ""
    assert "Owner-authored descriptions" not in render_descriptions(spaces)


def test_classify_context_loads_persisted_description(auth):
    auth.put(
        "/api/spaces/work/description", json={"description": "School follow-ups", "updated_at": ""}
    )
    conn = db.connect(auth.app.state.settings.db_path)
    try:
        ctx = classify_context(conn)
    finally:
        conn.close()
    assert next(s for s in ctx if s.name == "work").description == "School follow-ups"


def test_description_reaches_runner_and_redo_context(ai_client, monkeypatch, tmp_path):
    ai_client.put(
        "/api/spaces/home/description",
        json={"description": "Family-school follow-ups", "updated_at": ""},
    )
    record = tmp_path / "classifier.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_classify_reply(monkeypatch, proposal(shape="note", space="work", confidence=0.95))
    capture(ai_client, "First capture about a project")
    assert '- home: "Family-school follow-ups"' in records(record)[-1]["argv"][-1]

    set_classify_reply(monkeypatch, proposal(shape="note", space="home", confidence=0.5))
    item = capture(ai_client, "A waiting school follow-up")["items"][0]
    set_classify_reply(monkeypatch, proposal(shape="note", space="home", confidence=0.5))
    assert (
        ai_client.post(f"/api/items/{item['id']}/redo", json={"reason": "school"}).status_code
        == 200
    )
    assert '- home: "Family-school follow-ups"' in records(record)[-1]["argv"][-1]


def test_token_strictly_advances_on_a_frozen_or_backward_clock(tmp_path, monkeypatch):
    from datetime import UTC, datetime

    from tartib import space_descriptions

    class Frozen(datetime):
        moment = datetime(2026, 10, 7, 12, 0, 0, 500_000, tzinfo=UTC)

        @classmethod
        def now(cls, tz=None):
            return cls.moment

    monkeypatch.setattr(space_descriptions, "datetime", Frozen)
    conn = db.connect(str(tmp_path / "clock.db"))
    db.migrate(conn)
    conn.execute("INSERT INTO spaces(name, position, created_at) VALUES ('work',0,'now')")
    conn.commit()
    tokens = [""]
    for text in ("a", "a", ""):  # a same-text save and a clear advance the token too
        tokens.append(set_space_description(conn, "work", text, tokens[-1])["updated_at"])
    assert tokens[1:] == sorted(set(tokens[1:])) and len(set(tokens)) == 4
    Frozen.moment = Frozen.moment.replace(second=0)  # the clock steps back a minute
    back = set_space_description(conn, "work", "b", tokens[-1])["updated_at"]
    assert back > tokens[-1]
    conn.close()


def test_space_context_budget_is_enforced_by_the_combined_logic_at_any_size():
    spaces = tuple(
        SpaceContext(f"s{i}", 5, 5, tuple(f"item {i}-{j} " + "y" * 60 for j in range(4)), "d" * 90)
        for i in range(6)
    )
    full_descriptions = render_descriptions(spaces, DESCRIPTION_BUDGET)
    for budget in (10, 40, 200, 1_000, 3_000, 12_000):
        descriptions, existing = render_space_context(spaces, budget)
        assert len(descriptions) + len(existing) <= budget, budget
    # Room for the full descriptions plus a little: the descriptions stay whole and the
    # example block gives way, never the other way round.
    descriptions, existing = render_space_context(spaces, len(full_descriptions) + 600)
    assert descriptions == full_descriptions
    assert len(existing) <= 600
    # Too little room left over for even the shortening marker: still bounded.
    descriptions, existing = render_space_context(spaces, len(full_descriptions) + 20)
    assert len(descriptions) + len(existing) <= len(full_descriptions) + 20


def test_example_block_keeps_its_own_4000_cap_when_descriptions_are_short_or_absent():
    def many(description):
        return tuple(
            SpaceContext(
                f"s{i}", 5, 5, tuple(f"item {i}-{j} " + "z" * 80 for j in range(8)), description
            )
            for i in range(30)
        )

    for description in ("", "short purpose"):
        descriptions, existing = render_space_context(many(description))
        assert 0 < len(existing) <= 4_000
        assert len(descriptions) + len(existing) <= SPACE_CONTEXT_BUDGET
