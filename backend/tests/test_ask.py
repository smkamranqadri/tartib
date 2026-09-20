"""POST /api/ask: retrieval, fallback, prompt content, and the answer contract."""

import json

import pytest

from tartib.ask import retrieval_query
from tests.conftest import (
    capture,
    proposal,
    records,
    set_ask_reply,
    set_classify_reply,
    set_terms_reply,
)


@pytest.mark.parametrize(
    "q, expected",
    [
        ("what did I decide about the database?", '"database"*'),
        ("Postgres or SQLite?", '"postgres"* OR "sqlite"*'),
        ("gym", '"gym"'),
        ("what did I say?", ""),
        ("", ""),
        ("2026 plans", '"2026"* OR "plans"*'),
    ],
)
def test_retrieval_query(q, expected):
    assert retrieval_query(q) == expected


def seed(client, monkeypatch, texts):
    """Capture each text and file it as a note in the given space via the fake classifier."""
    ids = []
    for space, text in texts:
        set_classify_reply(monkeypatch, proposal(shape="note", text=text, space=space))
        ids.append(capture(client, text)["items"][0]["id"])
    return ids


def test_ask_retrieves_matches_and_cites(ai_client, monkeypatch, tmp_path):
    db_id, gym_id, _ = seed(
        ai_client,
        monkeypatch,
        [
            ("work", "Decided: use SQLite with FTS5 for Tartib, no Postgres."),
            ("health", "Gym on Tuesdays and Fridays, mornings."),
            ("work", "Standup moved to 10:30."),
        ],
    )
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "You chose SQLite with FTS5.", [db_id, 999, db_id])
    r = ai_client.post("/api/ask", json={"question": "what did I decide about sqlite vs postgres?"})
    assert r.status_code == 200
    body = r.json()
    assert body["answer"] == "You chose SQLite with FTS5."
    assert body["item_ids"] == [db_id]  # unknown and duplicate ids dropped
    assert body["items"][0]["id"] == db_id
    assert body["matched"] is True
    prompt = records(record)[-1]["argv"][-1]
    assert prompt.startswith("You answer one person's question using only their own captured")
    assert "Current datetime:" in prompt and "(Asia/Karachi)" in prompt
    assert "For status questions" in prompt
    assert f"[id {db_id}] " in prompt and "space: work · note" in prompt
    assert "SQLite with FTS5" in prompt
    assert f"[id {gym_id}]" not in prompt  # only FTS matches are sent
    assert "Question: what did I decide about sqlite vs postgres?" in prompt


def test_task_header_carries_status(ai_client, monkeypatch, tmp_path):
    set_classify_reply(
        monkeypatch,
        proposal(
            shape="task",
            text="ship the invoice",
            space="finance",
            title="Ship the invoice",
            due="2026-09-20",
        ),
    )
    item = capture(ai_client, "ship the invoice")["items"][0]
    ai_client.patch(f"/api/items/{item['id']}", json={"status": "done"})
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Done.", [item["id"]])
    ai_client.post("/api/ask", json={"question": "invoice status?"})
    prompt = records(record)[-1]["argv"][-1]
    assert f"[id {item['id']}] " in prompt
    assert "task: Ship the invoice · due 2026-09-20 · done" in prompt


def test_ask_falls_back_to_recent_in_space(ai_client, monkeypatch, tmp_path):
    ids = seed(
        ai_client,
        monkeypatch,
        [("work", "alpha note"), ("home", "beta note"), ("work", "gamma note")],
    )
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Nothing on that.", [])
    r = ai_client.post("/api/ask", json={"question": "zzzz unknown", "space": "Work"})
    assert r.status_code == 200
    assert r.json()["matched"] is False and r.json()["item_ids"] == []
    prompt = records(record)[-1]["argv"][-1]
    assert f"[id {ids[0]}]" in prompt and f"[id {ids[2]}]" in prompt
    assert f"[id {ids[1]}]" not in prompt  # other space excluded


def test_ask_is_read_only(ai_client, monkeypatch):
    ids = seed(ai_client, monkeypatch, [("work", "immutable thing")])
    before = ai_client.get(f"/api/items/{ids[0]}").json()
    set_ask_reply(monkeypatch, "x", ids)
    ai_client.post("/api/ask", json={"question": "immutable"})
    assert ai_client.get(f"/api/items/{ids[0]}").json() == before


def test_ask_with_no_items(ai_client, monkeypatch):
    r = ai_client.post("/api/ask", json={"question": "anything"})
    assert r.status_code == 200
    assert r.json() == {
        "answer": "There are no items to answer from yet.",
        "item_ids": [],
        "items": [],
        "matched": False,
        "expanded": False,
    }
    seed(ai_client, monkeypatch, [("work", "something")])
    r = ai_client.post("/api/ask", json={"question": "anything", "space": "travel"})
    assert r.status_code == 200 and r.json()["matched"] is False and r.json()["items"] == []


def test_ask_errors(ai_client, monkeypatch, auth):
    seed(ai_client, monkeypatch, [("work", "something")])
    monkeypatch.setenv("FAKE_CODEX_EXIT", "2")
    r = ai_client.post("/api/ask", json={"question": "something"})
    assert r.status_code == 502 and "ask failed" in r.json()["detail"]
    monkeypatch.delenv("FAKE_CODEX_EXIT")
    assert ai_client.post("/api/ask", json={"question": "   "}).status_code == 422
    assert auth.post("/api/ask", json={"question": "x"}).status_code == 503  # AI off


def test_ask_reply_shape_is_strict_json(ai_client, monkeypatch):
    seed(ai_client, monkeypatch, [("work", "something")])
    monkeypatch.setenv("FAKE_CODEX_REPLY_ASK", json.dumps({"answer": "", "item_ids": ["x", 1.5]}))
    body = ai_client.post("/api/ask", json={"question": "something"}).json()
    assert body["answer"] == "No answer." and body["item_ids"] == []


# --- slice 26: expansion when the question's own words find nothing, and one turn of carry ---


def _corpus(client, monkeypatch):
    """Five notes whose wording deliberately avoids the words the questions below use."""
    return seed(
        client,
        monkeypatch,
        [
            ("health", "Physio said swim twice a week for the shoulder."),
            ("health", "Bought new goggles and a kickboard."),
            ("health", "Lane 3 is quietest before 7am."),
            ("work", "Standup moved to 10:30."),
            ("work", "Ali said the API rate limit is 100 requests per minute."),
        ],
    )


def test_a_question_whose_own_words_find_nothing_is_answered_after_expansion(
    ai_client, monkeypatch, tmp_path
):
    swim, goggles, _, _, _ = _corpus(ai_client, monkeypatch)
    # Nothing in the corpus contains "cardio" or "routine".
    assert retrieval_query("what is my cardio routine?") == '"cardio"* OR "routine"*'

    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_terms_reply(monkeypatch, "swim", "physio", "goggles")
    set_ask_reply(monkeypatch, "Swimming twice a week.", [swim])
    r = ai_client.post("/api/ask", json={"question": "what is my cardio routine?"})

    body = r.json()
    assert body["matched"] is True and body["expanded"] is True
    assert body["item_ids"] == [swim]
    calls = records(record)
    assert [c["terms"] for c in calls] == [True, False]  # expansion first, then the answer
    prompt = calls[-1]["argv"][-1]
    for item_id in (swim, goggles):
        assert f"[id {item_id}] " in prompt


def test_the_same_question_without_expansion_finds_nothing(ai_client, monkeypatch):
    """The other half of the check above: with no terms proposed, the cheap path is all there is."""
    _corpus(ai_client, monkeypatch)
    set_terms_reply(monkeypatch)  # the model proposes nothing
    set_ask_reply(monkeypatch, "I could not find it.", [])
    body = ai_client.post("/api/ask", json={"question": "what is my cardio routine?"}).json()
    assert body["matched"] is False and body["expanded"] is False


def test_a_question_that_already_matches_costs_exactly_one_call(ai_client, monkeypatch, tmp_path):
    _corpus(ai_client, monkeypatch)
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "Before 7am in lane 3.", [])
    body = ai_client.post("/api/ask", json={"question": "swim lane goggles physio shoulder"}).json()
    assert body["matched"] is True and body["expanded"] is False
    calls = records(record)
    assert len(calls) == 1 and calls[0]["ask"] is True


def test_expansion_failing_does_not_fail_the_question(ai_client, monkeypatch):
    """A broken expansion call must leave the question no worse off than before the feature."""
    _corpus(ai_client, monkeypatch)
    monkeypatch.setenv("FAKE_CODEX_REPLY_TERMS", "not json at all")
    set_ask_reply(monkeypatch, "Nothing on that.", [])
    r = ai_client.post("/api/ask", json={"question": "what is my cardio routine?"})
    assert r.status_code == 200
    assert r.json()["expanded"] is False


def test_follow_up_resolves_against_the_previous_answer(ai_client, monkeypatch, tmp_path):
    """The backlog's own worked example: 'what about the second one?' has no content words."""
    swim, goggles, lane, _, _ = _corpus(ai_client, monkeypatch)
    # Its words are searchable but match nothing in the corpus: the same dead end.

    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_ask_reply(monkeypatch, "The goggles and kickboard.", [goggles])
    body = ai_client.post(
        "/api/ask",
        json={
            "question": "what about the second one?",
            "prior_question": "what did physio say?",
            "prior_item_ids": [swim, goggles, lane],
        },
    ).json()

    assert body["matched"] is False  # the question's own words matched nothing
    assert body["item_ids"] == [goggles]
    prompt = records(record)[-1]["argv"][-1]
    assert "Just before this, you were asked: what did physio say?" in prompt
    assert f"in this order: {swim}, {goggles}, {lane}" in prompt
    # The prior items lead the candidate list, in the order they were answered in.
    assert prompt.index(f"[id {swim}] ") < prompt.index(f"[id {goggles}] ")


def test_no_prior_turn_leaves_the_prompt_as_it_was(ai_client, monkeypatch, tmp_path):
    _corpus(ai_client, monkeypatch)
    record = tmp_path / "calls.jsonl"
    monkeypatch.setenv("FAKE_CODEX_RECORD", str(record))
    set_terms_reply(monkeypatch, "swim")
    set_ask_reply(monkeypatch, "ok", [])
    ai_client.post("/api/ask", json={"question": "what is my cardio routine?"})
    assert "Just before this" not in records(record)[-1]["argv"][-1]


def test_terms_query_cannot_carry_fts_syntax():
    from tartib.ask import terms_query

    # The quote and the bare MATCH cannot survive: every term comes back quoted.
    assert terms_query(['swim" OR items_fts MATCH "']) == '"swim"* OR "items_fts"* OR "match"*'
    assert terms_query(["swim", "swim"]) == '"swim"*'
    assert terms_query([]) == ""
