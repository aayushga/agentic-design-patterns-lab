"""Fake SDK proposals only; no credentials or live calls are needed."""
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

app = importlib.import_module("patterns.21-exploration-discovery.app")
module = importlib.import_module("patterns.21-exploration-discovery.openai_version.openai_discovery")


def response(config_id="cfg-01",*,raw=None,status="completed"):
    return SimpleNamespace(status=status,output_text=json.dumps({"config_id":config_id}) if raw is None else raw)


@pytest.fixture
def sdk(monkeypatch):
    def install(*outputs):
        state = {"requests":[],"clients":[],"closed":0}
        remaining = iter(outputs)
        class Client:
            def __init__(self,**kwargs):
                state["clients"].append(kwargs)
                self.responses = SimpleNamespace(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self,*args):
                state["closed"] += 1
            def create(self,**kwargs):
                state["requests"].append(kwargs)
                output = next(remaining)
                if isinstance(output,Exception):
                    raise output
                return output
        monkeypatch.setitem(sys.modules,"openai",SimpleNamespace(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY","offline-placeholder")
        return state
    return install


def test_missing_key_has_clear_error_before_sdk_import(monkeypatch):
    monkeypatch.setitem(sys.modules,"openai",None)
    with pytest.raises(ValueError,match="Missing OPENAI_API_KEY"):
        module.run_openai_discovery()


def test_no_proposal_needed_requires_neither_key_nor_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules,"openai",None)
    for kwargs in [{"max_model_requests":0},{"max_experiments":0},{"cost_budget":0},{"cost_budget":1},
                   {"max_experiments":1},{"target_latency_ms":120}]:
        result = module.run_openai_discovery(**kwargs)
        assert result.model_attempts == 0
    assert module.run_openai_discovery(max_model_requests=0).report.target_met


def test_missing_optional_sdk_has_actionable_error(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY","offline-placeholder")
    monkeypatch.setitem(sys.modules,"openai",None)
    with pytest.raises(ValueError,match="requirements.txt"):
        module.run_openai_discovery()


def test_request_contract_uses_only_offered_candidates_and_real_evidence(sdk):
    state = sdk(response(),response("cfg-03"))
    result = module.run_openai_discovery()
    assert result.model_attempts == len(state["requests"]) == 2
    assert state["closed"] == 2
    assert all(c == {"api_key":"offline-placeholder","timeout":30.0,"max_retries":0} for c in state["clients"])
    first,second = state["requests"]
    for request in state["requests"]:
        assert request["model"] == "gpt-6-astra" and request["reasoning"] == {"effort":"low"}
        assert request["max_output_tokens"] == 1000 and request["store"] is False
        assert request["text"]["format"]["strict"] is True
        assert not request["text"]["format"]["schema"]["additionalProperties"]
        assert "temperature" not in request
    payload = json.loads(first["input"])
    assert {c["config_id"] for c in payload["candidates"]} == {"cfg-01","cfg-02","cfg-04"}
    assert len(payload["evidence"]) == 1 and payload["evidence"][0]["latency_ms"] == 120
    assert all("latency_ms" not in c for c in payload["candidates"])
    second_payload = json.loads(second["input"])
    assert [e["latency_ms"] for e in second_payload["evidence"]] == [120,80]
    assert "cfg-00" not in [c["config_id"] for c in second_payload["candidates"]]
    assert result.report.best_latency_ms == 45 and result.report.target_met
    assert result.report.trials[-1].selection_source == "proposal"


@pytest.mark.parametrize("raw", ['{"config_id":"cfg-00"}','{"config_id":"cfg-07"}',
    '{"config_id":"invented"}','{"config_id":["cfg-01"]}',
    '{"config_id":"cfg-01","latency_ms":1}', '{}','null','not JSON','', 'x'*257])
def test_invalid_proposal_stops_future_model_calls_and_keeps_real_measurements(sdk,raw):
    state = sdk(response(raw=raw))
    result = module.run_openai_discovery()
    assert result.model_attempts == len(state["requests"]) == state["closed"] == 1
    assert result.report.target_met and result.report.best_latency_ms == 45
    assert result.report.trials[1].selection_source == "rules_fallback"
    assert result.report.trials[1].selection_reason == "invalid_output"
    assert result.report.trials[1].latency_ms == 80
    assert result.report.trials[2].selection_reason == "model_stopped"


def test_provider_failure_is_not_experimental_failure_and_does_not_retry(sdk):
    state = sdk(RuntimeError("PRIVATE_PROVIDER_ERROR"))
    result = module.run_openai_discovery()
    assert result.model_attempts == len(state["requests"]) == state["closed"] == 1
    assert result.report.trials[1].selection_reason == "provider_error"
    assert not result.report.failed_config_ids and result.report.target_met
    assert "PRIVATE_PROVIDER_ERROR" not in repr(result)


def test_incomplete_generation_stops_model_and_falls_back(sdk):
    state = sdk(response(status="incomplete"))
    result = module.run_openai_discovery()
    assert result.report.trials[1].selection_reason == "generation_not_completed"
    assert result.model_attempts == state["closed"] == 1
    assert result.report.target_met


def test_model_budget_exhaustion_continues_with_local_rules(sdk):
    state = sdk(response())
    result = module.run_openai_discovery(max_model_requests=1)
    assert result.model_attempts == len(state["requests"]) == 1
    assert result.report.trials[-1].selection_reason == "model_budget_exhausted"
    assert result.report.target_met


def test_three_call_cap_and_budget_eligibility_are_host_enforced(sdk):
    state = sdk(response("cfg-01"),response("cfg-03"),response("cfg-07"))
    result = module.run_openai_discovery(target_latency_ms=1)
    assert result.model_attempts == len(state["requests"]) == state["closed"] == 3
    assert result.report.trials[3].status == "failed" and result.report.trials[3].latency_ms is None
    assert result.report.trials[4].selection_reason == "model_budget_exhausted"
    assert result.report.spent_cost_units == 8 and not result.report.target_met


@pytest.mark.parametrize("explicit,expected", [(None,"environment-model"),("explicit-model","explicit-model")])
def test_model_precedence(monkeypatch,sdk,explicit,expected):
    monkeypatch.setenv("OPENAI_MODEL","environment-model")
    state = sdk(response())
    result = module.run_openai_discovery(model=explicit,max_model_requests=1)
    assert result.model == expected and state["requests"][0]["model"] == expected


@pytest.mark.parametrize("limit", [-1,4,True,None,1.5])
def test_invalid_model_limits_precede_credentials(limit,monkeypatch):
    monkeypatch.setitem(sys.modules,"openai",None)
    with pytest.raises(ValueError,match="max_model_requests"):
        module.run_openai_discovery(max_model_requests=limit)


def test_invalid_host_budgets_precede_sdk(sdk):
    state = sdk(response())
    with pytest.raises(ValueError,match="cost_budget"):
        module.run_openai_discovery(cost_budget=-1)
    assert not state["clients"]


def test_unaffordable_frontier_choice_is_withheld_and_rejected(sdk):
    state = sdk(response("cfg-01"),response("cfg-03"))
    result = module.run_openai_discovery(cost_budget=3,target_latency_ms=40)
    offered = json.loads(state["requests"][1]["input"])["candidates"]
    assert {c["config_id"] for c in offered} == {"cfg-04","cfg-05"}
    assert all(c["cost_units"] == 1 for c in offered)
    assert result.report.trials[-1].config_id == "cfg-05"
    assert result.report.trials[-1].selection_reason == "invalid_output"
    assert result.report.spent_cost_units == 3 and result.report.remaining_cost_units == 0
    assert result.report.stop_reason == "cost_limit" and not result.report.target_met
