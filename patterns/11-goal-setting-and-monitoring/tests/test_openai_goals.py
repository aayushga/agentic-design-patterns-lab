"""Model chooses actions; observed simulator state determines goal completion."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.11-goal-setting-and-monitoring.openai_version.openai_goals")
app = importlib.import_module("patterns.11-goal-setting-and-monitoring.app")


def action(kind="triage", ticket_id="T-1"):
    return json.dumps({"kind": kind, "ticket_id": ticket_id})


@pytest.fixture
def sdk(monkeypatch):
    def install(*outputs, status="completed", error=None):
        pending, requests, clients = iter(outputs), [], []
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


def execute(**kwargs):
    return module.run_openai_goal((app.Ticket("T-1"),), app.Goal(("T-1",)), **kwargs)


def test_observed_failure_context_and_progress_are_in_next_model_requests(sdk):
    requests, clients = sdk(action(), action("collect_context"), action())
    tickets = (app.Ticket("T-1", context_ready=False),)
    result = module.run_openai_goal(tickets, app.Goal(("T-1",)))
    assert result.status == "completed" and len(requests) == 3
    assert [s.observation.status for s in result.history] == ["blocked", "success", "success"]
    second = json.loads(requests[1]["input"])
    assert second["history"][0]["observation"]["status"] == "blocked"
    assert second["progress"]["triaged"] == 0 and not second["tickets"][0]["context_ready"]
    third = json.loads(requests[2]["input"])
    assert third["tickets"][0]["context_ready"] and third["progress"]["triaged"] == 0
    assert all(r["model"] == "gpt-6-astra" and r["reasoning"] == {"effort": "low"} for r in requests)
    assert all(r["store"] is False and r["text"]["format"]["strict"] for r in requests)
    assert len(clients) == 1 and clients[0]["closed"]
    assert clients[0]["options"]["max_retries"] == 0 and clients[0]["options"]["timeout"] == 30
    assert not tickets[0].triaged


@pytest.mark.parametrize("raw", ["not JSON", "[]", "{}", '{"completed":true}',
    '{"kind":"resolve","ticket_id":"T-1"}', '{"kind":"triage","ticket_id":"outside"}',
    '{"kind":"triage","ticket_id":1}', '{"kind":"triage","ticket_id":"T-1","success":true}'])
def test_invalid_model_action_cannot_claim_success_or_mutate_inputs(sdk, raw):
    requests, clients = sdk(raw)
    with pytest.raises(ValueError):
        execute()
    assert len(requests) == 1 and clients[0]["closed"]


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("failed", ""),
    ("completed", ""), ("completed", " "), ("completed", None)])
def test_incomplete_or_refused_output_is_not_completion(sdk, status, text):
    _, clients = sdk(text, status=status)
    with pytest.raises(RuntimeError):
        execute()
    assert clients[0]["closed"]


def test_api_failure_closes_client_without_retry(sdk):
    requests, clients = sdk(error=RuntimeError("API unavailable"))
    with pytest.raises(RuntimeError, match="unavailable"):
        execute()
    assert len(requests) == 1 and clients[0]["closed"]


def test_missing_key_before_sdk_creation(sdk, monkeypatch):
    requests, clients = sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        execute()
    assert not requests and not clients


def test_invalid_scope_before_sdk_creation(sdk):
    requests, clients = sdk()
    with pytest.raises(ValueError):
        module.run_openai_goal((app.Ticket("T-2"),), app.Goal(("T-1",)))
    assert not requests and not clients


def test_already_complete_works_without_key_or_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    result = module.run_openai_goal((app.Ticket("T-1", triaged=True),), app.Goal(("T-1",)))
    assert result.status == "completed" and not result.history


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(sdk, monkeypatch, explicit, expected):
    requests, _ = sdk(action())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    execute(model=explicit)
    assert requests[0]["model"] == expected


def test_step_budget_caps_billable_attempts(sdk):
    requests, clients = sdk(action("collect_context"))
    result = module.run_openai_goal((app.Ticket("T-1", context_ready=False),),
                                    app.Goal(("T-1",), max_steps=1, deadline_seconds=2))
    assert result.status == "step_limit" and len(requests) == 1 and clients[0]["closed"]
    assert clients[0]["options"]["timeout"] == 2


def test_stall_budget_stops_unhelpful_model_calls(sdk):
    requests, _ = sdk(action("collect_context"), action("collect_context"))
    result = execute()
    assert result.status == "stalled" and len(requests) == 2 and result.progress.triaged == 0


def test_failed_model_attempt_consumes_chooser_budget(sdk):
    requests, _ = sdk(error=RuntimeError("failed"))
    from openai import OpenAI
    with OpenAI() as client:
        chooser = module.OpenAIChooser(client, module.DEFAULT_MODEL, 1)
        goal, tickets = app.Goal(("T-1",)), (app.Ticket("T-1"),)
        args = (goal, tickets, app.measure(tickets, goal), ())
        with pytest.raises(RuntimeError):
            chooser(*args)
        with pytest.raises(ValueError, match="request limit"):
            chooser(*args)
    assert len(requests) == chooser.requests_used == 1
