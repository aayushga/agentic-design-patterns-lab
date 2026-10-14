"""Offline checks for fresh memory snapshots, control costs, budgets, and failures."""
from copy import deepcopy
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.08-memory-management.openai_version.openai_memory")
app = importlib.import_module("patterns.08-memory-management.app")


@pytest.fixture
def store(tmp_path):
    with app.MemoryStore(tmp_path / "memory.sqlite3") as memory:
        yield memory


@pytest.fixture
def memory_sdk(monkeypatch):
    def install(*outputs, status="completed", error=None):
        pending = iter(outputs)
        requests = []
        clients = []
        class Client:
            def __init__(self, **kwargs):
                self.state = {"options": kwargs, "closed": False}
                clients.append(self.state)
                self.responses = NS(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.state["closed"] = True
            def create(self, **kwargs):
                requests.append(kwargs)
                if error:
                    raise error
                return NS(status=status, output_text=next(pending))
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def test_second_request_receives_profile_state_and_previous_turn(store, memory_sdk):
    requests, clients = memory_sdk("First reply", "Follow-up reply")
    session = app.Session("alice", "first", max_turns=2)
    responder = module.OpenAIResponder()
    module.run_openai_turn("remember reply_style = concise", session, store, responder=responder)
    assert not requests
    module.run_openai_turn("issue: Upload fails.", session, store, responder=responder)
    result = module.run_openai_turn("What issue did I mention?", session, store, responder=responder)
    context = json.loads(requests[1]["input"])["memory_context"]
    assert context["long_term_facts"] == {"reply_style": "concise"}
    assert context["session_state"] == {"current_issue": "Upload fails."}
    assert context["recent_turns"] == [{"query": "issue: Upload fails.", "response": "First reply"}]
    assert result.response == "Follow-up reply" and responder.requests_used == 2
    assert all(r["store"] is False and r["reasoning"] == {"effort": "low"} for r in requests)
    assert all(r["model"] == "gpt-6-astra" and "previous_response_id" not in r for r in requests)
    assert all(c["closed"] and c["options"]["max_retries"] == 0 and c["options"]["timeout"] == 30.0 for c in clients)


def test_controls_work_without_api_key_or_sdk_import(store, monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    session = app.Session("alice", "first")
    for query in ["remember reply_style = concise", "recall reply_style", "forget reply_style", "reset session"]:
        result = module.run_openai_turn(query, session, store)
        assert result.memory_action != "chat"
    assert not session.history and store.snapshot("alice")[1] == {}


def test_request_window_is_bounded_and_issue_state_retained(store, memory_sdk):
    requests, _ = memory_sdk("Reply one", "Reply two", "Reply three", "Reply four")
    session = app.Session("alice", "first", max_turns=2)
    responder = module.OpenAIResponder()
    for query in ["issue: Upload fails.", "Follow-up one", "Follow-up two", "Follow-up three"]:
        module.run_openai_turn(query, session, store, responder=responder)
    context = json.loads(requests[-1]["input"])["memory_context"]
    assert [turn["query"] for turn in context["recent_turns"]] == ["Follow-up one", "Follow-up two"]
    assert context["session_state"]["current_issue"] == "Upload fails."
    assert len(session.history) == 2


def test_reopened_user_profile_is_sent_without_other_users_data(store, memory_sdk):
    store.remember("alice", "reply_style", "concise")
    store.remember("bob", "preferred_language", "spanish")
    requests, _ = memory_sdk("Reply")
    module.run_openai_turn("Hello", app.Session("alice", "new"), store)
    context = json.loads(requests[0]["input"])["memory_context"]
    assert context["long_term_facts"] == {"reply_style": "concise"}
    assert context["recent_turns"] == [] and context["session_state"] == {}
    assert "bob" not in json.dumps(context)


def test_forget_removes_saved_fact_and_stale_replies_from_next_request(store, memory_sdk):
    requests, _ = memory_sdk("Your preference is concise", "Reply after forgetting")
    first, second = app.Session("alice", "first"), app.Session("alice", "second")
    responder = module.OpenAIResponder()
    app.chat("remember reply_style = concise", first, store)
    module.run_openai_turn("Hello", second, store, responder=responder)
    module.run_openai_turn("forget reply_style", first, store, responder=responder)
    module.run_openai_turn("Next", second, store, responder=responder)
    context = json.loads(requests[-1]["input"])["memory_context"]
    assert context["long_term_facts"] == {} and context["recent_turns"] == []
    assert "concise" not in requests[-1]["input"]


def test_budget_stops_model_calls_but_memory_controls_still_work(store, memory_sdk):
    requests, clients = memory_sdk("Reply")
    responder = module.OpenAIResponder(max_requests=1)
    session = app.Session("alice", "first")
    module.run_openai_turn("Hello", session, store, responder=responder)
    before = deepcopy(session.history)
    with pytest.raises(ValueError, match="request limit"):
        module.run_openai_turn("issue: Upload fails.", session, store, responder=responder)
    assert len(requests) == len(clients) == 1 and session.history == before and not session.state
    module.run_openai_turn("remember reply_style = concise", session, store, responder=responder)
    assert responder.requests_used == 1 and store.snapshot("alice")[1]["reply_style"] == "concise"


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("failed", ""),
                                        ("completed", ""), ("completed", " "), ("completed", None)])
def test_unusable_response_does_not_commit_state_or_history(store, memory_sdk, status, text):
    requests, clients = memory_sdk(text, status=status)
    session = app.Session("alice", "first")
    responder = module.OpenAIResponder()
    with pytest.raises(RuntimeError):
        module.run_openai_turn("issue: Upload fails.", session, store, responder=responder)
    assert not session.history and not session.state
    assert responder.requests_used == 1 and clients[0]["closed"] and len(requests) == 1


def test_api_error_counts_attempt_and_preserves_memory(store, memory_sdk):
    requests, clients = memory_sdk(error=RuntimeError("API unavailable"))
    session = app.Session("alice", "first")
    app.chat("remember reply_style = concise", session, store)
    responder = module.OpenAIResponder()
    with pytest.raises(RuntimeError, match="API unavailable"):
        module.run_openai_turn("issue: Upload fails.", session, store, responder=responder)
    assert responder.requests_used == 1 and len(requests) == 1 and clients[0]["closed"]
    assert not session.history and not session.state
    assert store.snapshot("alice")[1] == {"reply_style": "concise"}


def test_missing_key_before_client_creation_or_state_commit(store, memory_sdk, monkeypatch):
    requests, clients = memory_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    session = app.Session("alice", "first")
    responder = module.OpenAIResponder()
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_turn("issue: Upload fails.", session, store, responder=responder)
    assert not requests and not clients and responder.requests_used == 0
    assert not session.history and not session.state


@pytest.mark.parametrize("query", ["", " ", None, "remember password = secret", "issue: "])
def test_invalid_query_does_not_make_request(store, memory_sdk, query):
    requests, clients = memory_sdk()
    with pytest.raises(ValueError):
        module.run_openai_turn(query, app.Session("alice", "first"), store)
    assert not requests and not clients


@pytest.mark.parametrize("limit", [0, 21, True, 1.5])
def test_invalid_model_budget(limit):
    with pytest.raises(ValueError, match="max_requests"):
        module.OpenAIResponder(max_requests=limit)


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(store, memory_sdk, monkeypatch, explicit, expected):
    requests, _ = memory_sdk("Reply")
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_turn("Hello", app.Session("alice", "first"), store, model=explicit)
    assert requests[0]["model"] == expected


def test_model_argument_cannot_conflict_with_shared_responder(store, memory_sdk):
    requests, _ = memory_sdk()
    with pytest.raises(ValueError, match="shared responder"):
        module.run_openai_turn("Hello", app.Session("alice", "first"), store,
                               responder=module.OpenAIResponder(), model="gpt-6-astra")
    assert not requests
