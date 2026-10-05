"""Exercise the optional SDK interface without installing it or calling an API."""
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

router = importlib.import_module("patterns.04-reflection.openai_version.openai_reflection")
ACCEPT = json.dumps({"approved": True, "issues": []})
REJECT = json.dumps({"approved": False, "issues": ["add a next step"]})


@pytest.fixture
def reflection_sdk(monkeypatch):
    def install(*outputs, status="completed", error=None):
        pending = iter(outputs)
        requests = []
        state = {"closed": False, "options": None}

        class Client:
            def __init__(self, **kwargs):
                state["options"] = kwargs
                self.responses = SimpleNamespace(create=self.create)

            def __enter__(self):
                return self

            def __exit__(self, *args):
                state["closed"] = True

            def create(self, **kwargs):
                requests.append(kwargs)
                if error:
                    raise error
                return SimpleNamespace(status=status, output_text=next(pending))

        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, state
    return install


def test_draft_feedback_revision_and_final_review(reflection_sdk):
    requests, state = reflection_sdk("first", REJECT, "improved", ACCEPT)
    result = router.run_openai_reflection("ticket")
    assert result.approved and result.final_draft == "improved"
    assert result.revisions == 1 and len(requests) == 4
    assert json.loads(requests[1]["input"]) == {"ticket": "ticket", "draft": "first"}
    assert json.loads(requests[2]["input"]) == {
        "ticket": "ticket", "draft": "first", "issues": ["add a next step"]}
    assert json.loads(requests[3]["input"])["draft"] == "improved"
    assert "writer" in requests[0]["instructions"] and "critic" in requests[1]["instructions"]
    assert requests[1]["text"]["format"]["strict"] is True
    assert "text" not in requests[0]
    assert all(r["model"] == "gpt-6-astra" and r["reasoning"] == {"effort": "low"} for r in requests)
    assert state["options"]["max_retries"] == 0 and state["options"]["timeout"] == 30.0
    assert state["closed"]


def test_early_approval_uses_two_requests(reflection_sdk):
    requests, _ = reflection_sdk("ready", ACCEPT)
    result = router.run_openai_reflection("ticket")
    assert result.approved and result.revisions == 0 and len(requests) == 2


def test_supplied_draft_uses_only_critic(reflection_sdk):
    requests, _ = reflection_sdk(ACCEPT)
    result = router.run_openai_reflection("ticket", initial_draft="ready")
    assert result.initial_draft == "ready" and len(requests) == 1


def test_default_budget_caps_requests_and_reviews_final_draft(reflection_sdk):
    requests, _ = reflection_sdk("first", REJECT, "second", REJECT, "third", REJECT)
    result = router.run_openai_reflection("ticket")
    assert not result.approved and result.stop_reason == "revision_limit"
    assert result.revisions == 2 and len(requests) == 6
    assert json.loads(requests[-1]["input"])["draft"] == result.final_draft == "third"


def test_repeated_revision_stops_early(reflection_sdk):
    requests, _ = reflection_sdk("first", REJECT, "first")
    result = router.run_openai_reflection("ticket")
    assert result.stop_reason == "no_progress" and not result.approved
    assert len(requests) == 3 and result.final_draft == "first"


@pytest.mark.parametrize("raw", [
    "not JSON", "[]", '{"approved":true}', '{"approved":true,"issues":[],"extra":1}',
    '{"approved":"true","issues":[]}', '{"approved":true,"issues":["fix"]}',
    '{"approved":false,"issues":[]}', '{"approved":false,"issues":[""]}',
    '{"approved":false,"issues":"fix"}',
])
def test_malformed_critique_fails_and_closes_client(reflection_sdk, raw):
    requests, state = reflection_sdk("draft", raw)
    with pytest.raises(ValueError):
        router.run_openai_reflection("ticket")
    assert len(requests) == 2 and state["closed"]


@pytest.mark.parametrize("status,text", [
    ("incomplete", "partial"), ("failed", ""), ("completed", ""),
    ("completed", " "), ("completed", None),
])
def test_unusable_response_never_returns_approval(reflection_sdk, status, text):
    _, state = reflection_sdk(text, status=status)
    with pytest.raises(RuntimeError):
        router.run_openai_reflection("ticket")
    assert state["closed"]


def test_api_error_propagates_and_closes_client(reflection_sdk):
    _, state = reflection_sdk(error=RuntimeError("API unavailable"))
    with pytest.raises(RuntimeError, match="API unavailable"):
        router.run_openai_reflection("ticket")
    assert state["closed"]


def test_missing_key_prevents_client_creation(reflection_sdk, monkeypatch):
    requests, state = reflection_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        router.run_openai_reflection("ticket")
    assert not requests and state["options"] is None


@pytest.mark.parametrize("kwargs", [{"query": ""}, {"query": "ticket", "max_revisions": 6}])
def test_invalid_input_prevents_client_creation(reflection_sdk, kwargs):
    requests, state = reflection_sdk()
    with pytest.raises(ValueError):
        router.run_openai_reflection(**kwargs)
    assert not requests and state["options"] is None


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(reflection_sdk, monkeypatch, explicit, expected):
    requests, _ = reflection_sdk("draft", ACCEPT)
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    router.run_openai_reflection("ticket", model=explicit)
    assert all(request["model"] == expected for request in requests)
