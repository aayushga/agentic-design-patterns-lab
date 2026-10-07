"""Offline protocol checks for Responses function calling and result replay."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.05-tool-use.openai_version.openai_tool_use")
app = importlib.import_module("patterns.05-tool-use.app")


def tool_response(name="lookup_order", arguments=None, call_id="call-1", extra=None):
    call = NS(type="function_call", name=name, call_id=call_id,
              arguments=json.dumps({"order_id": "ORD-1001"} if arguments is None else arguments))
    return NS(status="completed", output=[*(extra or []), call], output_text="")


def answer(text="Demo order ORD-1001 is shipped (simulated data).", status="completed"):
    return NS(status=status, output=[NS(type="message")], output_text=text)


@pytest.fixture
def tool_sdk(monkeypatch):
    def install(*responses, error=None):
        pending = iter(responses)
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
                return next(pending)
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, state
    return install


def test_real_tool_result_and_reasoning_items_are_replayed(tool_sdk):
    reasoning = NS(type="reasoning", id="reasoning-1")
    first = tool_response(extra=[reasoning])
    requests, state = tool_sdk(first, answer())
    result = module.run_openai_tool_use("Status of ORD-1001")
    assert result.stop_reason == "completed" and len(result.tool_history) == 1
    assert result.tool_history[0].output["status"] == "shipped"
    assert requests[0]["input"] == [{"role": "user", "content": "Status of ORD-1001"}]
    replay = requests[1]["input"]
    assert replay[1] is reasoning and replay[2] is first.output[-1]
    assert replay[-1]["type"] == "function_call_output" and replay[-1]["call_id"] == "call-1"
    observation = json.loads(replay[-1]["output"])
    assert observation["status"] == "success" and observation["output"]["status"] == "shipped"
    assert all(r["parallel_tool_calls"] is False and r["reasoning"] == {"effort": "low"} for r in requests)
    assert all(r["model"] == "gpt-6-astra" for r in requests)
    assert state["options"]["timeout"] == 30.0 and state["options"]["max_retries"] == 0
    assert state["closed"]
    for definition in requests[0]["tools"]:
        assert definition["strict"] is True
        assert definition["parameters"]["additionalProperties"] is False
        assert set(definition["parameters"]["required"]) == set(definition["parameters"]["properties"])


def test_two_tools_return_each_observation_once(tool_sdk):
    requests, _ = tool_sdk(tool_response(),
        tool_response("calculate", {"operation": "add", "left": 120, "right": 10}, "call-2"),
        answer("Demo total: 130 USD (simulated data)."))
    result = module.run_openai_tool_use("Total for ORD-1001")
    assert result.tool_history[-1].output["value"] == 130
    outputs = [x for x in requests[-1]["input"] if isinstance(x, dict) and x.get("type") == "function_call_output"]
    assert [x["call_id"] for x in outputs] == ["call-1", "call-2"]
    assert "Remaining tool calls: 1" in requests[-1]["instructions"]


@pytest.mark.parametrize("name,args", [("unknown_tool", {}), ("lookup_order", []),
    ("lookup_order", {"order_id": "ORD-9999"}), ("lookup_order", {}),
    ("calculate", {"operation": "divide", "left": 1, "right": 0})])
def test_tool_error_is_returned_to_model(tool_sdk, name, args):
    requests, _ = tool_sdk(tool_response(name, args), answer("Unable to retrieve or calculate this result."))
    result = module.run_openai_tool_use("ticket")
    assert result.tool_history[0].status == "error" and result.tool_history[0].output is None
    payload = json.loads(requests[1]["input"][-1]["output"])
    assert payload["status"] == "error" and payload["error"]


def test_no_tool_answer_uses_one_request(tool_sdk):
    requests, _ = tool_sdk(answer("Please provide an order ID."))
    result = module.run_openai_tool_use("Where is my order?")
    assert not result.tool_history and len(requests) == 1


@pytest.mark.parametrize("budget", [0, 1, 3, 5])
def test_repeated_requests_hit_budget_without_extra_execution(tool_sdk, monkeypatch, budget):
    responses = [tool_response(call_id=f"call-{n}") for n in range(budget + 1)]
    requests, state = tool_sdk(*responses)
    executions = []
    monkeypatch.setitem(app.TOOLS, "lookup_order", lambda **kwargs: executions.append(kwargs) or {})
    result = module.run_openai_tool_use("ticket", max_tool_calls=budget)
    assert len(requests) == budget + 1 and len(executions) == budget
    assert result.stop_reason == "tool_limit" and result.final_response is None and state["closed"]


def test_answer_at_budget_boundary_is_allowed(tool_sdk):
    requests, _ = tool_sdk(tool_response(), answer())
    assert module.run_openai_tool_use("ticket", max_tool_calls=1).stop_reason == "completed"
    assert len(requests) == 2


@pytest.mark.parametrize("raw", ["not JSON", '{"order_id":', '{"left":NaN}', '{"right":Infinity}'])
def test_malformed_arguments_fail_before_execution(tool_sdk, monkeypatch, raw):
    response = tool_response()
    response.output[0].arguments = raw
    _, state = tool_sdk(response)
    monkeypatch.setitem(app.TOOLS, "lookup_order", lambda **kwargs: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="malformed"):
        module.run_openai_tool_use("ticket")
    assert state["closed"]


def test_multiple_calls_rejected_before_any_execution(tool_sdk, monkeypatch):
    response = tool_response()
    response.output += tool_response(call_id="call-2").output
    _, state = tool_sdk(response)
    monkeypatch.setitem(app.TOOLS, "lookup_order", lambda **kwargs: pytest.fail("must not execute"))
    with pytest.raises(ValueError, match="at most one"):
        module.run_openai_tool_use("ticket")
    assert state["closed"]


def test_duplicate_id_is_a_protocol_error(tool_sdk):
    _, state = tool_sdk(tool_response(), tool_response())
    with pytest.raises(ValueError, match="Duplicate"):
        module.run_openai_tool_use("ticket")
    assert state["closed"]


@pytest.mark.parametrize("text,status", [("", "completed"), (" ", "completed"),
    (None, "completed"), ("partial", "incomplete"), ("", "failed")])
def test_empty_refusal_or_incomplete_response_never_succeeds(tool_sdk, text, status):
    _, state = tool_sdk(answer(text, status))
    with pytest.raises((ValueError, RuntimeError)):
        module.run_openai_tool_use("ticket")
    assert state["closed"]


def test_unexpected_output_type_fails(tool_sdk):
    response = answer()
    response.output = [NS(type="custom_tool_call")]
    tool_sdk(response)
    with pytest.raises(ValueError, match="Unexpected"):
        module.run_openai_tool_use("ticket")


def test_sdk_failure_propagates_and_closes_client(tool_sdk):
    _, state = tool_sdk(error=RuntimeError("API unavailable"))
    with pytest.raises(RuntimeError, match="API unavailable"):
        module.run_openai_tool_use("ticket")
    assert state["closed"]


def test_missing_key_before_client_creation(tool_sdk, monkeypatch):
    requests, state = tool_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_tool_use("ticket")
    assert not requests and state["options"] is None


@pytest.mark.parametrize("kwargs", [{"query": ""}, {"query": "ticket", "max_tool_calls": 6}])
def test_input_validated_before_client_creation(tool_sdk, kwargs):
    requests, state = tool_sdk()
    with pytest.raises(ValueError):
        module.run_openai_tool_use(**kwargs)
    assert not requests and state["options"] is None


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(tool_sdk, monkeypatch, explicit, expected):
    requests, _ = tool_sdk(answer())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_tool_use("ticket", model=explicit)
    assert requests[0]["model"] == expected
