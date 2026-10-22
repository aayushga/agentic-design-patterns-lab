"""The optional SDK is faked; every test runs without a key or live request."""
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

app = importlib.import_module("patterns.20-prioritization.app")
module = importlib.import_module("patterns.20-prioritization.openai_version.openai_prioritization")


def response(ids=None, *, raw=None, status="completed"):
    return SimpleNamespace(status=status,output_text=raw if raw is not None else
                           json.dumps({"ranked_task_ids":["notes","metrics","feedback"] if ids is None else ids}))


@pytest.fixture
def sdk(monkeypatch):
    def install(output):
        state = {"requests":[],"closed":False}
        class Client:
            def __init__(self,**kwargs):
                state["options"] = kwargs
                self.responses = SimpleNamespace(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self,*args):
                state["closed"] = True
            def create(self,**kwargs):
                state["requests"].append(kwargs)
                if isinstance(output,Exception):
                    raise output
                return output
        monkeypatch.setitem(sys.modules,"openai",SimpleNamespace(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY","offline-placeholder")
        return state
    return install


def test_key_missing_before_import(monkeypatch):
    monkeypatch.setitem(sys.modules,"openai",None)
    with pytest.raises(ValueError,match="Missing OPENAI_API_KEY"):
        module.run_openai_prioritization()


def test_no_eligible_or_disabled_budget_needs_neither_sdk_nor_key(monkeypatch):
    monkeypatch.setitem(sys.modules,"openai",None)
    disabled = module.run_openai_prioritization(max_model_requests=0)
    assert disabled.model_attempts == 0
    assert disabled.decision.ranking_source == "rules"
    assert disabled.decision.reason_code == "model_budget_disabled"
    assert disabled.decision.selected_task_id == "metrics"
    blocked = module.run_openai_prioritization(budget_minutes=0)
    assert blocked.model_attempts == 0 and blocked.decision.status == "blocked"
    empty = module.run_openai_prioritization(tasks=[])
    assert empty.model_attempts == 0 and empty.decision.status == "complete"


def test_request_contract_eligible_only_and_host_diagnostics(sdk):
    state = sdk(response())
    result = module.run_openai_prioritization()
    assert result.model_attempts == 1 and state["closed"]
    assert state["options"] == {"api_key":"offline-placeholder","timeout":30.0,"max_retries":0}
    request = state["requests"][0]
    assert request["model"] == "gpt-6-astra"
    assert request["reasoning"] == {"effort":"low"}
    assert request["max_output_tokens"] == 1500 and request["store"] is False
    assert "temperature" not in request
    payload = json.loads(request["input"])
    assert {t["task_id"] for t in payload["eligible_tasks"]} == {"metrics","notes","feedback"}
    assert "Fix checkout regression" not in request["input"]
    schema = request["text"]["format"]
    assert schema["strict"] and not schema["schema"]["additionalProperties"]
    assert set(schema["schema"]["properties"]["ranked_task_ids"]["items"]["enum"]) == {"metrics","notes","feedback"}
    assert result.decision.selected_task_id == "notes"
    assert result.decision.ranking_source == "openai"
    assert result.decision.ranked[0].rule_score == 14


@pytest.mark.parametrize("ids", [["fix","notes","feedback"],["metrics","metrics","feedback"],
    ["metrics"],["metrics","notes","invented"],["metrics","notes","feedback","fix"],
    ["metrics","notes",{}],[],None])
def test_invalid_ranking_uses_explicit_rules_fallback(sdk,ids):
    state = sdk(response(raw=json.dumps({"ranked_task_ids":ids})))
    result = module.run_openai_prioritization()
    assert result.decision.selected_task_id == "metrics"
    assert result.decision.ranking_source == "rules_fallback"
    assert result.decision.reason_code == "invalid_model_ranking"
    assert result.model_attempts == len(state["requests"]) == 1 and state["closed"]


@pytest.mark.parametrize("raw", ['{}','null','not JSON','[]','', 'x'*4097,
    '{"ranked_task_ids":["metrics","notes","feedback"],"completed":["fix"]}'])
def test_invalid_json_or_extra_fields_cannot_change_state(sdk,raw):
    sdk(response(raw=raw))
    result = module.run_openai_prioritization()
    assert result.decision.ranking_source == "rules_fallback"
    assert result.decision.reason_code == "invalid_model_ranking"


def test_incomplete_generation_is_not_a_valid_ranking(sdk):
    state = sdk(response(status="incomplete"))
    result = module.run_openai_prioritization()
    assert result.decision.reason_code == "generation_not_completed"
    assert result.decision.selected_task_id == "metrics" and state["closed"]


def test_provider_error_is_bounded_and_exception_text_not_returned(sdk):
    state = sdk(RuntimeError("PRIVATE_PROVIDER_MESSAGE"))
    result = module.run_openai_prioritization()
    assert len(state["requests"]) == result.model_attempts == 1
    assert result.decision.ranking_source == "rules_fallback"
    assert result.decision.reason_code == "provider_error"
    assert state["closed"] and "PRIVATE_PROVIDER_MESSAGE" not in repr(result)


@pytest.mark.parametrize("explicit,expected", [(None,"environment-model"),("explicit-model","explicit-model")])
def test_model_precedence(monkeypatch,sdk,explicit,expected):
    monkeypatch.setenv("OPENAI_MODEL","environment-model")
    state = sdk(response())
    assert module.run_openai_prioritization(model=explicit).model == expected
    assert state["requests"][0]["model"] == expected


@pytest.mark.parametrize("limit", [-1,2,True,None,1.5])
def test_bad_model_budget_precedes_key_or_import(monkeypatch,limit):
    monkeypatch.setitem(sys.modules,"openai",None)
    with pytest.raises(ValueError,match="max_model_requests"):
        module.run_openai_prioritization(max_model_requests=limit)


def test_invalid_host_context_precedes_model(sdk):
    state = sdk(response())
    with pytest.raises(ValueError,match="dependency"):
        module.run_openai_prioritization(tasks=[app.Task("one","Work",3,5,dependencies=("missing",))])
    assert not state["requests"]


def test_model_cannot_get_unarrived_or_unavailable_candidates(sdk):
    tasks = [app.Task("one","Allowed",1,1),app.Task("future","PRIVATE_FUTURE",5,1,created_minute=10),
             app.Task("resource","PRIVATE_RESOURCE",5,1,resource="reporting"),
             app.Task("large","PRIVATE_TOO_LARGE",5,120)]
    state = sdk(response(["one"]))
    result = module.run_openai_prioritization(tasks=tasks,budget_minutes=2)
    assert result.decision.selected_task_id == "one"
    assert "PRIVATE_" not in state["requests"][0]["input"]
