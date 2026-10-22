"""Fake SDK responses exercise the same reservations without live API calls."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

app = importlib.import_module("patterns.16-resource-aware-optimization.app")
module = importlib.import_module("patterns.16-resource-aware-optimization.openai_version.openai_optimizer")
BRIEF = app.WorkItem("Report a login problem.")
DETAILED = app.WorkItem(BRIEF.query, "detailed")


class ConnectionError(Exception):
    pass


class StatusError(Exception):
    def __init__(self, status, code=None):
        self.status_code, self.code = status, code


@pytest.fixture
def sdk(monkeypatch):
    monkeypatch.delenv("OPENAI_ECONOMY_MODEL", raising=False)
    def install(*responses):
        requests, clients = [], []
        remaining = iter(responses)
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
                result = next(remaining)
                if isinstance(result, Exception):
                    raise result
                return result
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client, APIConnectionError=ConnectionError, APIStatusError=StatusError))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def response(text="Ask support to review.", status="completed", code=None):
    return NS(output_text=text, status=status, error=NS(code=code))


def test_missing_key_before_sdk_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        with module.openai_agent():
            pytest.fail("Should not create an agent")


@pytest.mark.parametrize("detail,effort,cap", [("brief", "low", 600), ("detailed", "medium", 1600)])
def test_profile_request_options_and_cleanup(sdk, detail, effort, cap):
    requests, clients = sdk(response())
    with module.openai_agent() as agent:
        result = agent.answer(app.WorkItem(BRIEF.query, detail))
        cached = agent.answer(app.WorkItem(BRIEF.query, detail))
    assert result.status == "answered" and cached.status == "cached"
    assert len(requests) == 1 and result.reserved_output_tokens == cap
    request = requests[0]
    assert request["model"] == "gpt-6-astra"
    assert request["reasoning"] == {"effort": effort} and request["max_output_tokens"] == cap
    assert request["store"] is False and 0 < request["timeout"] <= 30
    assert json.loads(request["input"]) == {"query": BRIEF.query, "detail": detail}
    assert "temperature" not in request and "previous_response_id" not in request
    assert clients[0]["closed"] and clients[0]["options"] == {"api_key": "offline-placeholder", "timeout": 30.0, "max_retries": 0}


@pytest.mark.parametrize("explicit,env,expected", [(None, None, "gpt-6-astra"),
    (None, "environment-model", "environment-model"), ("explicit-model", "environment-model", "explicit-model")])
def test_main_model_precedence(sdk, monkeypatch, explicit, env, expected):
    requests, _ = sdk(response())
    if env:
        monkeypatch.setenv("OPENAI_MODEL", env)
    with module.openai_agent(model=explicit) as agent:
        agent.answer(DETAILED)
    assert requests[0]["model"] == expected


def test_separate_economy_model_precedence(sdk, monkeypatch):
    requests, _ = sdk(response())
    monkeypatch.setenv("OPENAI_ECONOMY_MODEL", "environment-economy")
    with module.openai_agent(model="main-model", economy_model="explicit-economy") as agent:
        agent.answer(BRIEF)
    assert requests[0]["model"] == "explicit-economy"


def test_environment_economy_model_is_used(sdk, monkeypatch):
    requests, _ = sdk(response())
    monkeypatch.setenv("OPENAI_ECONOMY_MODEL", "environment-economy")
    with module.openai_agent() as agent:
        agent.answer(BRIEF)
    assert requests[0]["model"] == "environment-economy"


@pytest.mark.parametrize("failure", [ConnectionError(), StatusError(503), StatusError(429, "rate_limit_exceeded"),
    response(status="failed", code="server_error"), response(status="failed", code="rate_limit_exceeded")])
def test_transient_failure_fallback_reserves_both_attempts(sdk, failure):
    requests, clients = sdk(failure, response())
    with module.openai_agent() as agent:
        result = agent.answer(DETAILED)
    assert result.status == "degraded" and result.reserved_output_tokens == 2200
    assert [r["max_output_tokens"] for r in requests] == [1600, 600]
    assert clients[0]["closed"]


@pytest.mark.parametrize("failure", [StatusError(401), StatusError(400), StatusError(403),
    StatusError(429, "insufficient_quota"), StatusError(429), response(status="incomplete"),
    response(status="failed", code="invalid_prompt"), response(""), response(None), response("x" + " " * 3000)])
def test_terminal_or_invalid_response_never_triggers_another_paid_attempt(sdk, failure):
    requests, clients = sdk(failure)
    with module.openai_agent() as agent:
        result = agent.answer(DETAILED)
    assert result.status == "failed" and not result.answer
    assert result.reserved_output_tokens == 1600 and len(requests) == 1
    assert clients[0]["closed"]


def test_no_eligible_profile_means_no_model_request(sdk):
    requests, clients = sdk()
    with module.openai_agent(app.Budget(output_tokens=0)) as agent:
        result = agent.answer(DETAILED)
    assert result.status == "blocked" and requests == [] and clients[0]["closed"]


def test_failure_cannot_spend_reserved_tokens_again(sdk):
    requests, _ = sdk(ConnectionError())
    with module.openai_agent(app.Budget(output_tokens=1600)) as agent:
        first = agent.answer(DETAILED)
        second = agent.answer(BRIEF)
    assert first.status == "unavailable" and second.status == "blocked"
    assert len(requests) == 1
