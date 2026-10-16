"""Real MCP with fake model responses: discovery, execution, replay, and bounds."""
import asyncio
from contextlib import asynccontextmanager
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

if sys.version_info < (3, 11):
    pytest.skip("MCP SDK v2 requires Python 3.11+; legacy patterns still run on 3.10", allow_module_level=True)

from mcp import Client

module = importlib.import_module("patterns.10-model-context-protocol.openai_version.openai_mcp")
server_module = importlib.import_module("patterns.10-model-context-protocol.server")


def tool(name="get_ticket", arguments=None, call_id="call-1", extra=None):
    call = NS(type="function_call", name=name, call_id=call_id,
              arguments=json.dumps({"ticket_id": "T-101"} if arguments is None else arguments))
    return NS(status="completed", output=[*(extra or []), call], output_text="")


def final(text="Demo ticket T-101 reports a duplicate charge (simulated data).", status="completed"):
    return NS(status=status, output=[NS(type="message")], output_text=text)


class FakeAPI:
    def __init__(self, *outputs, error=None):
        self.outputs = iter(outputs)
        self.requests = []
        self.error = error
        self.responses = NS(create=self.create)
    async def create(self, **kwargs):
        self.requests.append(kwargs)
        if self.error:
            raise self.error
        return next(self.outputs)


def execute(api, **kwargs):
    async def run():
        error, result = None, None
        async with Client(server_module.create_server()) as client:
            try:
                result = await module.run_model_loop("What is reported in T-101?", client, api, **kwargs)
            except Exception as exc:
                error = exc
        if error:
            raise error
        return result
    return asyncio.run(run())


def test_discovered_schema_actual_mcp_result_and_reasoning_replay():
    reasoning = NS(type="reasoning", id="reasoning-1")
    first = tool(extra=[reasoning])
    api = FakeAPI(first, final())
    result = execute(api)
    assert result.status == "completed" and len(result.tool_history) == 1
    assert result.tool_history[0].output["ticket"]["ticket_id"] == "T-101"
    assert sorted(result.discovered_tools) == ["get_ticket", "list_tickets"]
    definitions = {item["name"]: item for item in api.requests[0]["tools"]}
    assert definitions["get_ticket"]["parameters"]["properties"]["ticket_id"]["pattern"] == r"^T-\d{3}$"
    assert all(item["strict"] and item["parameters"]["additionalProperties"] is False for item in definitions.values())
    context = json.loads(api.requests[0]["input"][0]["content"])["mcp_context"]
    assert "simulated" in context["policy"] and "T-101" in context["prompt"]
    replay = api.requests[1]["input"]
    assert replay[1] is reasoning and replay[2] is first.output[-1]
    assert replay[-1]["type"] == "function_call_output" and replay[-1]["call_id"] == "call-1"
    payload = json.loads(replay[-1]["output"])
    assert payload["status"] == "success" and payload["output"]["source"] == "simulated demo data"
    assert all(item["model"] == "gpt-6-astra" and item["parallel_tool_calls"] is False for item in api.requests)
    assert all(item["reasoning"] == {"effort": "low"} for item in api.requests)


def test_two_mcp_calls_then_answer_at_budget_boundary():
    api = FakeAPI(tool("list_tickets", {"priority": "high"}),
                  tool(call_id="call-2"), final())
    result = execute(api)
    assert len(api.requests) == 3 and len(result.tool_history) == 2 and result.status == "completed"
    assert len(result.tool_history[0].output["tickets"]) == 2
    outputs = [item for item in api.requests[-1]["input"] if isinstance(item, dict) and item.get("type") == "function_call_output"]
    assert [item["call_id"] for item in outputs] == ["call-1", "call-2"]


@pytest.mark.parametrize("name,args", [("get_ticket", {"ticket_id": "T-999"}),
    ("get_ticket", {"ticket_id": "bad"}), ("get_ticket", {}),
    ("get_ticket", {"ticket_id": "T-101", "extra": 1}), ("shell", {})])
def test_errors_are_observed_by_model_without_fabricated_success(name, args):
    api = FakeAPI(tool(name, args), final("Unable to retrieve the requested data."))
    result = execute(api)
    assert result.tool_history[0].status == "error" and result.tool_history[0].output is None
    payload = json.loads(api.requests[-1]["input"][-1]["output"])
    assert payload["status"] == "error" and payload["error"]


@pytest.mark.parametrize("budget", [0, 1, 2, 5])
def test_budget_caps_model_and_mcp_calls(budget):
    api = FakeAPI(*(tool(call_id=f"call-{n}") for n in range(budget + 1)))
    result = execute(api, max_tool_calls=budget)
    assert len(api.requests) == budget + 1 and len(result.tool_history) == budget
    assert result.status == "tool_limit" and result.final_response is None


def test_no_tool_answer_uses_one_model_request():
    api = FakeAPI(final("Please provide a ticket ID."))
    result = execute(api)
    assert len(api.requests) == 1 and not result.tool_history


@pytest.mark.parametrize("raw", ["not JSON", "[]", '{"ticket_id":', '{"ticket_id":NaN}'])
def test_malformed_arguments_never_execute(raw, monkeypatch):
    response = tool()
    response.output[-1].arguments = raw
    async def forbidden(*args):
        pytest.fail("Malformed calls must not execute")
    monkeypatch.setattr(module, "call_tool", forbidden)
    with pytest.raises(ValueError):
        execute(FakeAPI(response))


def test_multiple_calls_rejected_before_any_execution(monkeypatch):
    response = tool()
    response.output.extend(tool(call_id="other").output)
    async def forbidden(*args):
        pytest.fail("Must reject the whole response")
    monkeypatch.setattr(module, "call_tool", forbidden)
    with pytest.raises(ValueError, match="at most one"):
        execute(FakeAPI(response))


def test_duplicate_call_id_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        execute(FakeAPI(tool(), tool()))


@pytest.mark.parametrize("text,status", [("", "completed"), (None, "completed"),
    ("partial", "incomplete"), ("", "failed")])
def test_unusable_model_response_is_not_a_final_answer(text, status):
    with pytest.raises((ValueError, RuntimeError)):
        execute(FakeAPI(final(text, status)))


def test_api_error_propagates():
    with pytest.raises(RuntimeError, match="API unavailable"):
        execute(FakeAPI(error=RuntimeError("API unavailable")))


def test_no_allowed_discovered_functions_is_an_error():
    with pytest.raises(ValueError, match="No allowed"):
        module.function_definitions([NS(name="shell")])


@pytest.fixture
def owned_clients(monkeypatch):
    def install(*responses, error=None):
        api = FakeAPI(*responses, error=error)
        state = {"mcp_closed": False, "api_closed": False, "mcp_open": False, "options": None}
        @asynccontextmanager
        async def connect():
            state["mcp_open"] = True
            try:
                yield NS()
            finally:
                state["mcp_closed"] = True
        class API:
            def __init__(self, **kwargs):
                state["options"] = kwargs
            async def __aenter__(self):
                return api
            async def __aexit__(self, *args):
                state["api_closed"] = True
        async def loop(query, client, api_client, **kwargs):
            state["model"] = kwargs["model"]
            if error:
                raise error
            return module.MCPAgentResult(query, [], "completed", "Reply", [])
        monkeypatch.setattr(module, "connect_local", connect)
        monkeypatch.setattr(module, "run_model_loop", loop)
        monkeypatch.setitem(sys.modules, "openai", NS(AsyncOpenAI=API))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return state
    return install


def test_owned_clients_close_on_failure(owned_clients):
    state = owned_clients(error=RuntimeError("failed"))
    with pytest.raises(RuntimeError):
        asyncio.run(module.run_openai_mcp("Ticket query"))
    assert state["api_closed"] and state["mcp_closed"]
    assert state["options"]["max_retries"] == 0 and state["options"]["timeout"] == 30.0


def test_missing_key_before_mcp_start(owned_clients, monkeypatch):
    state = owned_clients()
    monkeypatch.delenv("OPENAI_API_KEY")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        asyncio.run(module.run_openai_mcp("Ticket query"))
    assert not state["mcp_open"] and state["options"] is None


@pytest.mark.parametrize("query,budget", [("", 2), (None, 2), ("query", -1), ("query", 6), ("query", True)])
def test_invalid_input_before_mcp_start(owned_clients, query, budget):
    state = owned_clients()
    with pytest.raises(ValueError):
        asyncio.run(module.run_openai_mcp(query, max_tool_calls=budget))
    assert not state["mcp_open"]


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(owned_clients, monkeypatch, explicit, expected):
    state = owned_clients()
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    asyncio.run(module.run_openai_mcp("Ticket query", model=explicit))
    assert state["model"] == expected and state["api_closed"] and state["mcp_closed"]
