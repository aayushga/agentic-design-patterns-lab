"""Offline request and communication checks for distinct OpenAI role prompts."""
from dataclasses import asdict
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.07-multi-agent-collaboration.openai_version.openai_collaboration")
app = importlib.import_module("patterns.07-multi-agent-collaboration.app")
QUERY = "I was charged twice. The app crashes during upload."
ASSIGN_BOTH = json.dumps({"roles": ["billing", "technical"], "reason": "Both concerns reported"})
BILLING = json.dumps({"findings": [asdict(item) for item in app.billing_specialist(QUERY)]})
TECHNICAL = json.dumps({"findings": [asdict(item) for item in app.technical_specialist(QUERY)]})


@pytest.fixture
def role_sdk(monkeypatch):
    def install(*outputs):
        pending = iter(outputs)
        requests = []
        state = {"closed": False, "options": None}
        class Client:
            def __init__(self, **kwargs):
                state["options"] = kwargs
                self.responses = NS(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                state["closed"] = True
            def create(self, **kwargs):
                requests.append(kwargs)
                output = next(pending)
                if isinstance(output, Exception):
                    raise output
                if isinstance(output, tuple):
                    status, output = output
                else:
                    status = "completed"
                return NS(status=status, output_text=output)
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, state
    return install


def test_supervisor_specialists_and_writer_have_distinct_requests(role_sdk):
    requests, state = role_sdk(ASSIGN_BOTH, BILLING, TECHNICAL, "Combined support reply")
    result = module.run_openai_collaboration(QUERY)
    assert result.status == "completed" and result.final_response == "Combined support reply"
    assert len(requests) == 4 and state["closed"]
    assert "supervise" in requests[0]["instructions"]
    assert "billing specialist" in requests[1]["instructions"]
    assert "technical specialist" in requests[2]["instructions"]
    assert "reply writer" in requests[3]["instructions"]
    assert all(json.loads(request["input"])["query"] == QUERY for request in requests)
    assert "handoffs" not in json.loads(requests[1]["input"])
    handoffs = json.loads(requests[-1]["input"])["handoffs"]
    assert [item["sender"] for item in handoffs] == ["billing", "technical"]
    assert all(item["recipient"] == "writer" and item["status"] == "success" for item in handoffs)
    assert handoffs[0]["findings"] == json.loads(BILLING)["findings"]
    assert handoffs[1]["findings"] == json.loads(TECHNICAL)["findings"]
    assert requests[0]["text"]["format"]["strict"] is True
    assert requests[1]["text"]["format"]["strict"] is True
    assert "text" not in requests[-1]
    assert all(r["model"] == "gpt-6-astra" and r["reasoning"] == {"effort": "low"} for r in requests)
    assert all("temperature" not in r for r in requests)
    assert state["options"]["max_retries"] == 0 and state["options"]["timeout"] == 30.0


def test_single_specialist_uses_three_requests(role_sdk):
    requests, _ = role_sdk('{"roles":["billing"],"reason":"Billing only"}', BILLING, "Reply")
    result = module.run_openai_collaboration(QUERY)
    assert result.assignment.roles == ["billing"] and len(requests) == 3
    assert [item.sender for item in result.handoffs] == ["billing"]


def test_no_assigned_roles_skips_specialists_and_writer(role_sdk):
    requests, state = role_sdk('{"roles":[],"reason":"Need details"}')
    result = module.run_openai_collaboration("Hello")
    assert result.status == "needs_clarification" and len(requests) == 1 and state["closed"]


@pytest.mark.parametrize("raw", ["not JSON", "[]", '{}', '{"roles":"billing","reason":"x"}',
    '{"roles":["arbitrary"],"reason":"x"}', '{"roles":["billing","billing"],"reason":"x"}',
    '{"roles":["billing"],"reason":""}', '{"roles":[],"reason":"x","extra":1}'])
def test_invalid_supervisor_output_stops_before_specialist_request(role_sdk, raw):
    requests, state = role_sdk(raw)
    with pytest.raises(ValueError):
        module.run_openai_collaboration(QUERY)
    assert len(requests) == 1 and state["closed"]


@pytest.mark.parametrize("failure", [RuntimeError("sensitive-sdk-details"), "not JSON",
    '{"findings":[]}', '{"findings":[{}]}', '{"findings":null}',
    '{"findings":[{"evidence":"invented","assessment":"x","next_step":"y"}]}',
    ("incomplete", "partial"), ("completed", ""), ("completed", None)])
def test_specialist_failure_reaches_writer_as_error_handoff(role_sdk, failure):
    requests, state = role_sdk(ASSIGN_BOTH, BILLING, failure, "Partial reply")
    result = module.run_openai_collaboration(QUERY)
    assert result.status == "needs_review" and "human review" in result.final_response
    assert len(requests) == 4 and state["closed"]
    handoffs = json.loads(requests[-1]["input"])["handoffs"]
    assert handoffs[0]["status"] == "success" and handoffs[1]["status"] == "error"
    assert handoffs[1]["findings"] == [] and handoffs[1]["error"]
    assert "sensitive-sdk-details" not in str(result)


def test_all_specialists_fail_skips_writer(role_sdk):
    requests, state = role_sdk(ASSIGN_BOTH, RuntimeError("billing unavailable"), RuntimeError("technical unavailable"))
    result = module.run_openai_collaboration(QUERY)
    assert result.status == "failed" and result.final_response is None
    assert len(requests) == 3 and state["closed"]


@pytest.mark.parametrize("failure", [RuntimeError("writer unavailable"), "", " ", None, ("incomplete", "partial")])
def test_writer_failure_preserves_validated_handoffs(role_sdk, failure):
    _, state = role_sdk(ASSIGN_BOTH, BILLING, TECHNICAL, failure)
    result = module.run_openai_collaboration(QUERY)
    assert result.status == "failed" and result.final_response is None and result.writer_error
    assert all(item.status == "success" for item in result.handoffs) and state["closed"]


@pytest.mark.parametrize("failure", [RuntimeError("supervisor unavailable"), ("incomplete", "partial"),
                                     ("completed", ""), ("completed", None)])
def test_supervisor_request_failure_propagates_and_closes_client(role_sdk, failure):
    requests, state = role_sdk(failure)
    with pytest.raises(RuntimeError):
        module.run_openai_collaboration(QUERY)
    assert len(requests) == 1 and state["closed"]


def test_missing_key_before_client_creation(role_sdk, monkeypatch):
    requests, state = role_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_collaboration(QUERY)
    assert not requests and state["options"] is None


@pytest.mark.parametrize("query", ["", " ", None])
def test_invalid_input_before_client_creation(role_sdk, query):
    requests, state = role_sdk()
    with pytest.raises(ValueError, match="non-empty"):
        module.run_openai_collaboration(query)
    assert not requests and state["options"] is None


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(role_sdk, monkeypatch, explicit, expected):
    requests, _ = role_sdk('{"roles":[],"reason":"Need details"}')
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_collaboration("Hello", model=explicit)
    assert requests[0]["model"] == expected


def test_first_specialist_failure_does_not_block_second_specialist(role_sdk):
    requests, state = role_sdk(ASSIGN_BOTH, RuntimeError("billing unavailable"), TECHNICAL, "Technical next steps")
    result = module.run_openai_collaboration(QUERY)
    assert result.status == "needs_review" and len(requests) == 4 and state["closed"]
    assert [item.status for item in result.handoffs] == ["error", "success"]
    assert result.handoffs[1].findings[0].evidence == "The app crashes during upload."
