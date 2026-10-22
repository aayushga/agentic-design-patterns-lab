"""Fake model proposals are accepted only after exact local verification."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

app = importlib.import_module("patterns.17-reasoning-techniques.app")
module = importlib.import_module("patterns.17-reasoning-techniques.openai_version.openai_reasoning")
GOOD = "8/(3-8/3)"
BAD = "(8-3)*(8-3)"


def output(*expressions):
    return NS(status="completed", output_text=json.dumps({"candidates": list(expressions)}))


@pytest.fixture
def sdk(monkeypatch):
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
                value = next(remaining)
                if isinstance(value, Exception):
                    raise value
                return value
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def test_missing_key_before_sdk_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_reasoning()


def test_valid_candidate_stops_after_one_request_and_request_is_bounded(sdk):
    requests, clients = sdk(output(BAD, GOOD))
    result = module.run_openai_reasoning()
    assert result.status == "solved" and result.solution == GOOD and result.model_attempts == 1
    assert [check.valid for check in result.checks] == [False, True]
    assert len(requests) == 1
    request = requests[0]
    assert request["model"] == "gpt-6-astra" and request["reasoning"] == {"effort": "medium"}
    assert request["max_output_tokens"] == 2000 and request["store"] is False
    assert request["text"]["format"]["strict"] is True
    assert json.loads(request["input"]) == {"puzzle": {"numbers": [3, 3, 8, 8], "target": 24}, "checked_proposals": []}
    assert "temperature" not in request and "previous_response_id" not in request
    assert clients[0]["closed"] and clients[0]["options"] == {"api_key": "offline-placeholder", "timeout": 30.0, "max_retries": 0}


def test_wrong_arithmetic_supplies_machine_feedback_to_one_correction(sdk):
    requests, clients = sdk(output(BAD), output(GOOD))
    result = module.run_openai_reasoning()
    assert result.status == "solved" and result.model_attempts == 2 and len(requests) == 2
    feedback = json.loads(requests[1]["input"])["checked_proposals"]
    assert feedback[0]["expression"] == BAD
    assert feedback[0]["error"] == "wrong_target" and feedback[0]["value"] == "25"
    assert feedback[0]["steps"][-1]["result"] == "25"
    assert clients[0]["closed"]


def test_all_wrong_candidates_abstain_at_model_budget(sdk):
    requests, _ = sdk(output(BAD), output(BAD))
    result = module.run_openai_reasoning()
    assert result.status == "unverified" and result.stop_reason == "model_budget"
    assert result.solution is None and result.model_attempts == 2 and len(requests) == 2


def test_one_attempt_budget_disables_correction(sdk):
    requests, _ = sdk(output(BAD))
    result = module.run_openai_reasoning(max_attempts=1)
    assert result.status == "unverified" and len(requests) == 1


def test_empty_candidates_stop_without_claiming_no_solution(sdk):
    requests, _ = sdk(output())
    result = module.run_openai_reasoning()
    assert result.status == "unverified" and result.stop_reason == "model_abstained"
    assert result.solution is None and len(requests) == 1


@pytest.mark.parametrize("raw", [None, "", "not JSON", "[]", "{}", '{"candidates":"wrong"}',
    json.dumps({"candidates": [GOOD] * 4}), json.dumps({"candidates": [24]}),
    json.dumps({"candidates": [GOOD.ljust(121)]}), json.dumps({"candidates": [GOOD], "extra": True}),
    " " * 2001])
def test_malformed_or_oversized_response_stops_without_another_attempt(sdk, raw):
    requests, clients = sdk(NS(status="completed", output_text=raw))
    result = module.run_openai_reasoning()
    assert result.status == "failed" and result.stop_reason == "invalid_model_output"
    assert not result.solution and len(requests) == 1 and clients[0]["closed"]


@pytest.mark.parametrize("status", ["failed", "incomplete", "cancelled"])
def test_non_completed_response_is_not_accepted_or_retried(sdk, status):
    requests, _ = sdk(NS(status=status, output_text=json.dumps({"candidates": [GOOD]})))
    result = module.run_openai_reasoning()
    assert result.status == "failed" and result.stop_reason == "model_not_completed"
    assert len(requests) == 1 and result.solution is None


def test_sdk_exception_is_safe_and_client_is_closed(sdk):
    requests, clients = sdk(RuntimeError("private backend credential"))
    result = module.run_openai_reasoning()
    assert result.status == "failed" and result.stop_reason == "model_request_failed"
    assert "private" not in str(result) and len(requests) == 1 and clients[0]["closed"]


@pytest.mark.parametrize("explicit,env,expected", [(None, None, "gpt-6-astra"),
    (None, "environment-model", "environment-model"), ("explicit-model", "environment-model", "explicit-model")])
def test_model_override_precedence(sdk, monkeypatch, explicit, env, expected):
    requests, _ = sdk(output(GOOD))
    if env:
        monkeypatch.setenv("OPENAI_MODEL", env)
    module.run_openai_reasoning(model=explicit)
    assert requests[0]["model"] == expected


@pytest.mark.parametrize("attempts", [0, 3, True, 1.5])
def test_invalid_attempt_budget_before_client_creation(sdk, attempts):
    requests, clients = sdk()
    with pytest.raises(ValueError):
        module.run_openai_reasoning(max_attempts=attempts)
    assert not requests and not clients
