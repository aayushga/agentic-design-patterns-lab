"""Offline checks for bounded context, persistence, namespaces, and forgetting."""
from copy import deepcopy
import importlib
import json
import sqlite3

import pytest

app = importlib.import_module("patterns.08-memory-management.app")


@pytest.fixture
def store(tmp_path):
    with app.MemoryStore(tmp_path / "memory.sqlite3") as memory:
        yield memory


def test_session_issue_and_explicit_preference_affect_replies(store):
    session = app.Session("alice", "first")
    remembered = app.chat("remember reply_style = concise", session, store)
    assert remembered.memory_action == "remembered" and not session.history
    app.chat("issue: Upload fails.", session, store)
    result = app.chat("What issue did I mention?", session, store)
    assert result.response == "Reported issue: Upload fails."
    assert result.session_state == {"current_issue": "Upload fails."}
    assert result.long_term_facts == {"reply_style": "concise"}
    assert result.short_term_turns == 2


def test_window_trims_old_turns_but_keeps_session_state(store):
    session = app.Session("alice", "first", max_turns=2)
    app.chat("issue: Upload fails.", session, store)
    for query in ["Next step?", "Any details?", "What did I say last?"]:
        result = app.chat(query, session, store)
    assert "Any details?" in result.response
    assert [turn.query for turn in session.history] == ["Any details?", "What did I say last?"]
    assert result.short_term_turns == 2 and result.session_state["current_issue"] == "Upload fails."


def test_profile_survives_database_reopen_but_session_issue_does_not(tmp_path):
    path = tmp_path / "memory.sqlite3"
    with app.MemoryStore(path) as store:
        first = app.Session("alice", "first")
        app.chat("remember reply_style = concise", first, store)
        app.chat("issue: Upload fails.", first, store)
    with app.MemoryStore(path) as store:
        second = app.Session("alice", "second")
        result = app.chat("recall reply_style", second, store)
        assert result.long_term_facts == {"reply_style": "concise"}
        assert result.session_state == {} and not second.history
        assert "Describe your support issue" in app.chat("What issue did I mention?", second, store).response


def test_users_are_namespaced_even_with_same_session_label(store):
    alice, bob = app.Session("alice", "same"), app.Session("bob", "same")
    app.chat("remember reply_style = concise", alice, store)
    app.chat("issue: Alice issue.", alice, store)
    result = app.chat("recall reply_style", bob, store)
    assert result.long_term_facts == {} and "No saved" in result.response
    assert result.session_state == {}


def test_update_replaces_preference_and_clears_stale_history(store):
    session = app.Session("alice", "first")
    app.chat("remember reply_style = concise", session, store)
    app.chat("issue: Upload fails.", session, store)
    result = app.chat("remember reply_style = detailed", session, store)
    assert result.long_term_facts == {"reply_style": "detailed"} and not session.history
    assert result.session_state["current_issue"] == "Upload fails."
    assert "Please share" in app.chat("Next step?", session, store).response


def test_forgetting_invalidates_other_session_history_before_next_context(store):
    first, second = app.Session("alice", "first"), app.Session("alice", "second")
    app.chat("remember preferred_language = spanish", first, store)
    app.chat("issue: Upload fails.", second, store)
    assert "Problema indicado" in second.history[-1].response
    forgotten = app.chat("forget preferred_language", first, store)
    seen = []
    app.chat("Next step?", second, store, responder=lambda query, context: seen.append(context) or "Reply")
    assert forgotten.long_term_facts == {} and seen[0]["long_term_facts"] == {}
    assert seen[0]["recent_turns"] == [] and second.state["current_issue"] == "Upload fails."


def test_reset_clears_state_and_history_but_not_preferences(store):
    session = app.Session("alice", "first")
    app.chat("remember preferred_language = spanish", session, store)
    app.chat("issue: Upload fails.", session, store)
    result = app.chat("reset session", session, store)
    assert result.memory_action == "session_reset" and not session.history and not session.state
    assert result.long_term_facts == {"preferred_language": "spanish"}


def test_no_implicit_long_term_memory(store):
    session = app.Session("alice", "first")
    app.chat("I prefer concise replies.", session, store)
    assert store.snapshot("alice")[1] == {}
    assert len(session.history) == 1


def test_missing_recall_and_forget_are_explicit_noops(store):
    session = app.Session("alice", "first")
    assert "No saved" in app.chat("recall reply_style", session, store).response
    assert "No saved" in app.chat("forget reply_style", session, store).response
    assert store.snapshot("alice") == (0, {})


def test_sql_looking_user_id_does_not_read_or_modify_other_user(store):
    store.remember("alice", "reply_style", "concise")
    identifier = "alice' OR 1=1 --"
    assert store.snapshot(identifier) == (0, {})
    store.remember(identifier, "reply_style", "detailed")
    assert store.snapshot("alice")[1] == {"reply_style": "concise"}


def test_responder_receives_copies_and_only_current_user_context(store):
    store.remember("bob", "reply_style", "concise")
    session = app.Session("alice", "first")
    seen = []
    def responder(query, context):
        seen.append(deepcopy(context))
        context["session_state"]["current_issue"] = "tampered"
        context["long_term_facts"]["reply_style"] = "concise"
        return "Reply"
    result = app.chat("issue: Original issue.", session, store, responder=responder)
    assert seen[0]["long_term_facts"] == {} and seen[0]["user_id"] == "alice"
    assert result.session_state == {"current_issue": "Original issue."}
    assert result.long_term_facts == {}


@pytest.mark.parametrize("reply", [None, "", " ", 42, "x" * 4001])
def test_unusable_reply_does_not_commit_new_turn_or_issue(store, reply):
    session = app.Session("alice", "first")
    app.chat("issue: Old issue.", session, store)
    before = deepcopy(session.history)
    with pytest.raises(ValueError, match="Responder"):
        app.chat("issue: New issue.", session, store, responder=lambda *_: reply)
    assert session.history == before and session.state == {"current_issue": "Old issue."}


def test_responder_failure_does_not_commit_turn(store):
    session = app.Session("alice", "first")
    def broken(*args):
        raise RuntimeError("unavailable")
    with pytest.raises(RuntimeError):
        app.chat("issue: New issue.", session, store, responder=broken)
    assert not session.history and not session.state


@pytest.mark.parametrize("query", ["remember", "remember password = secret", "remember reply_style = loud",
    "remember preferred_language = klingon", "recall password", "forget password", "issue: ",
    "", " ", None, "x" * 1001])
def test_invalid_input_does_not_write_memory_or_call_responder(store, query):
    session = app.Session("alice", "first")
    with pytest.raises(ValueError):
        app.chat(query, session, store, responder=lambda *_: pytest.fail("must validate first"))
    assert not session.history and not session.state and store.snapshot("alice")[1] == {}


@pytest.mark.parametrize("user,session_id,window", [(None, "s", 3), ("", "s", 3), ("a" * 65, "s", 3),
    ("alice", "", 3), ("alice", "s", 0), ("alice", "s", 11), ("alice", "s", True)])
def test_invalid_session_configuration(user, session_id, window):
    with pytest.raises(ValueError):
        app.Session(user, session_id, window)


def test_session_cannot_be_rebound_to_another_user(store):
    session = app.Session("alice", "first")
    app.chat("issue: Private issue.", session, store)
    session.user_id = "bob"
    with pytest.raises(ValueError, match="identity"):
        app.chat("What issue did I mention?", session, store)


def test_corrupt_profile_fails_without_overwriting(store):
    with store.connection:
        store.connection.execute("INSERT INTO profiles VALUES (?, ?, ?)", ("alice", 1, '{"password":"secret"}'))
    with pytest.raises(ValueError, match="not overwritten"):
        store.remember("alice", "reply_style", "concise")
    raw = store.connection.execute("SELECT facts FROM profiles WHERE user_id = ?", ("alice",)).fetchone()[0]
    assert json.loads(raw) == {"password": "secret"}


def test_store_closes_connection_on_context_exit(tmp_path):
    with app.MemoryStore(tmp_path / "memory.sqlite3") as store:
        store.remember("alice", "reply_style", "concise")
    with pytest.raises(sqlite3.ProgrammingError):
        store.snapshot("alice")
