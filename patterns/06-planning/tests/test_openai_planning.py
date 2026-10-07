"""Offline checks of plan generation, semantic validation, and replanning context."""
from dataclasses import asdict
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.06-planning.openai_version.openai_planning")
app = importlib.import_module("patterns.06-planning.app")
REQUEST = app.PlanningRequest("Prepare an offsite proposal", 20, 600)


def plan_json(venues=None, catering=None):
    return json.dumps(asdict(app.local_planner(REQUEST, venues or set(), catering or set())))


@pytest.fixture
def planner_sdk(monkeypatch):
    def install(*outputs, status="completed", error=None):
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
                if error:
                    raise error
                return NS(status=status, output_text=next(pending))
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, state
    return install


def test_one_model_plan_then_local_execution(planner_sdk):
    requests, state = planner_sdk(plan_json())
    result = module.run_openai_planning(REQUEST.goal)
    assert result.status == "completed" and result.proposal["total_cost"] == 500
    assert result.proposal["booked"] is False and len(requests) == 1
    payload = json.loads(requests[0]["input"])
    assert payload["request"] == asdict(REQUEST)
    assert payload["venues"] == app.VENUES and payload["catering"] == app.CATERING
    assert payload["excluded_venues"] == []
    assert requests[0]["model"] == "gpt-6-astra"
    assert requests[0]["reasoning"] == {"effort": "low"}
    assert "temperature" not in requests[0] and "tools" not in requests[0]
    format_ = requests[0]["text"]["format"]
    assert format_["type"] == "json_schema" and format_["strict"] is True
    assert format_["schema"]["additionalProperties"] is False
    assert state["options"]["max_retries"] == 0 and state["options"]["timeout"] == 30.0
    assert state["closed"]


def test_model_replans_with_execution_discovered_exclusion(planner_sdk):
    requests, state = planner_sdk(plan_json(), plan_json({"cedar"}))
    result = module.run_openai_planning(REQUEST.goal, unavailable_venues=("cedar",))
    assert result.status == "completed" and result.replans == 1
    assert result.proposal["venue"] == "City Loft" and result.proposal["total_cost"] == 600
    assert len(requests) == 2 and state["closed"]
    assert json.loads(requests[1]["input"])["excluded_venues"] == ["cedar"]
    assert result.attempts[0].steps[0].status == "error"


def test_catering_failure_reaches_model_as_constraint(planner_sdk):
    first = app.local_planner(app.PlanningRequest("offsite", 20, 800), set(), set())
    second = app.local_planner(app.PlanningRequest("offsite", 20, 800), set(), {"sandwiches"})
    requests, _ = planner_sdk(json.dumps(asdict(first)), json.dumps(asdict(second)))
    result = module.run_openai_planning("offsite", budget=800, unavailable_catering=("sandwiches",))
    assert result.proposal["catering"] == "Buffet lunch"
    assert json.loads(requests[1]["input"])["excluded_catering"] == ["sandwiches"]


def test_no_feasible_plan_has_no_execution(planner_sdk, monkeypatch):
    requests, _ = planner_sdk('{"reason":"Budget too small","steps":[]}')
    monkeypatch.setattr(app, "execute_plan", lambda *_: pytest.fail("nothing to execute"))
    result = module.run_openai_planning("offsite", budget=450)
    assert result.status == "no_feasible_plan" and result.proposal is None and len(requests) == 1


def test_replan_limit_prevents_second_request(planner_sdk):
    requests, state = planner_sdk(plan_json())
    result = module.run_openai_planning("offsite", unavailable_venues=("cedar",), max_replans=0)
    assert result.status == "replan_limit" and result.proposal is None
    assert len(requests) == 1 and state["closed"]


def test_maximum_budget_caps_requests_at_three(planner_sdk):
    requests, _ = planner_sdk(plan_json(), plan_json({"cedar"}), plan_json({"cedar", "loft"}))
    result = module.run_openai_planning("offsite", unavailable_venues=("cedar", "loft"), max_replans=2)
    assert result.status == "no_feasible_plan" and result.replans == 2 and len(requests) == 3


@pytest.mark.parametrize("raw", ["not JSON", "[]", '{}', '{"reason":"x","steps":null}',
    '{"reason":"x","steps":[null]}', '{"reason":"x","steps":[{}]}',
    '{"reason":"x","steps":[],"extra":1}', '{"reason":"x","steps":[]}'])
def test_malformed_or_false_infeasible_plan_never_executes(planner_sdk, monkeypatch, raw):
    _, state = planner_sdk(raw)
    monkeypatch.setattr(app, "execute_plan", lambda *_: pytest.fail("must not execute"))
    with pytest.raises(ValueError):
        module.run_openai_planning("offsite")
    assert state["closed"]


@pytest.mark.parametrize("mutation", [
    lambda p: p["steps"][0].update(option="missing"),
    lambda p: p["steps"][0].update(action="book_and_pay"),
    lambda p: p["steps"][-1].update(depends_on=["venue"]),
    lambda p: p["steps"][0].update(option="garden"),
    lambda p: p["steps"][0].update(option="loft") or p["steps"][1].update(option="buffet"),
])
def test_semantically_invalid_model_plan_rejected_before_execution(planner_sdk, monkeypatch, mutation):
    parsed = json.loads(plan_json())
    mutation(parsed)
    _, state = planner_sdk(json.dumps(parsed))
    monkeypatch.setattr(app, "execute_plan", lambda *_: pytest.fail("must validate first"))
    with pytest.raises(ValueError):
        module.run_openai_planning("offsite")
    assert state["closed"]


def test_model_cannot_reuse_excluded_venue(planner_sdk):
    requests, state = planner_sdk(plan_json(), plan_json())
    with pytest.raises(ValueError, match="excluded venue"):
        module.run_openai_planning("offsite", unavailable_venues=("cedar",))
    assert len(requests) == 2 and state["closed"]


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("failed", ""),
                                        ("completed", ""), ("completed", " "), ("completed", None)])
def test_unusable_model_response_fails_and_closes(planner_sdk, status, text):
    _, state = planner_sdk(text, status=status)
    with pytest.raises(RuntimeError):
        module.run_openai_planning("offsite")
    assert state["closed"]


def test_api_failure_propagates_and_closes(planner_sdk):
    _, state = planner_sdk(error=RuntimeError("API unavailable"))
    with pytest.raises(RuntimeError, match="API unavailable"):
        module.run_openai_planning("offsite")
    assert state["closed"]


def test_missing_key_before_client_creation(planner_sdk, monkeypatch):
    requests, state = planner_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_planning("offsite")
    assert not requests and state["options"] is None


@pytest.mark.parametrize("kwargs", [{"goal": ""}, {"goal": "offsite", "attendees": 0},
    {"goal": "offsite", "budget": 0}, {"goal": "offsite", "max_replans": 3}])
def test_invalid_request_before_client_creation(planner_sdk, kwargs):
    requests, state = planner_sdk()
    with pytest.raises(ValueError):
        module.run_openai_planning(**kwargs)
    assert not requests and state["options"] is None


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(planner_sdk, monkeypatch, explicit, expected):
    requests, _ = planner_sdk(plan_json())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_planning("offsite", model=explicit)
    assert requests[0]["model"] == expected
