"""Offline tests for actual tool execution, observations, and loop bounds."""
import importlib

import pytest

app = importlib.import_module("patterns.05-tool-use.app")


def test_order_lookup_and_answer_use_observation():
    result = app.run_tool_use("Status of ORD-1001")
    assert result.stop_reason == "completed"
    assert "shipped" in result.final_response and "simulated" in result.final_response
    assert len(result.tool_history) == 1
    assert result.tool_history[0].output["order_id"] == "ORD-1001"


def test_dependent_total_uses_lookup_values():
    result = app.run_tool_use("Total for ORD-1002")
    lookup, calculation = result.tool_history
    assert lookup.name == "lookup_order" and calculation.name == "calculate"
    assert calculation.arguments["left"] == lookup.output["items_total"] == 45.0
    assert calculation.arguments["right"] == lookup.output["shipping_fee"] == 5.0
    assert calculation.output["value"] == 50.0
    assert "50.00 USD" in result.final_response


@pytest.mark.parametrize("query,value", [("calculate 12 + 8", 20), ("calculate 12 - 8", 4),
                                        ("calculate -2 * 8", -16), ("calculate 12 / 8", 1.5)])
def test_calculator_commands(query, value):
    result = app.run_tool_use(query)
    assert result.tool_history[0].output["value"] == value
    assert result.stop_reason == "completed"


def test_unknown_query_does_not_execute_any_tool():
    result = app.run_tool_use("hello")
    assert not result.tool_history and "Try" in result.final_response


@pytest.mark.parametrize("query,error", [("Status of ORD-9999", "not found"),
                                        ("calculate 1 / 0", "divide by zero")])
def test_tool_errors_are_observed_and_explained(query, error):
    result = app.run_tool_use(query)
    assert result.tool_history[0].status == "error"
    assert result.tool_history[0].output is None
    assert error in result.final_response


@pytest.mark.parametrize("name,args,error", [
    ("shell", {}, "Unknown tool"), ("lookup_order", {}, "exactly"),
    ("lookup_order", {"order_id": "ORD-1001", "extra": 1}, "exactly"),
    ("lookup_order", {"order_id": 1001}, "form"), ("lookup_order", [], "exactly"),
    ("calculate", {"operation": "power", "left": 2, "right": 3}, "operation"),
    ("calculate", {"operation": "add", "left": True, "right": 1}, "finite"),
    ("calculate", {"operation": "add", "left": "2", "right": 1}, "finite"),
    ("calculate", {"operation": "add", "left": float("nan"), "right": 1}, "finite"),
    ("calculate", {"operation": "add", "left": float("inf"), "right": 1}, "finite"),
    ("calculate", {"operation": "add", "left": 10**400, "right": 1}, "finite"),
])
def test_execution_boundary_rejects_invalid_calls(name, args, error):
    observation = app.execute_tool(app.ToolCall("call-1", name, args))
    assert observation.status == "error" and error in observation.error
    assert observation.output is None


def test_order_lookup_returns_a_copy():
    first = app.lookup_order("ORD-1001")
    first["status"] = "tampered"
    assert app.lookup_order("ORD-1001")["status"] == "shipped"


@pytest.mark.parametrize("budget", [0, 1, 3, 5])
def test_limit_bounds_execution_and_does_not_invent_answer(budget):
    decisions = []
    def decide(query, history):
        decisions.append(len(history))
        return app.Decision(tool_call=app.ToolCall(str(len(history)), "lookup_order", {"order_id": "ORD-1001"}))
    result = app.run_tool_use("ticket", decider=decide, max_tool_calls=budget)
    assert len(result.tool_history) == budget and len(decisions) == budget + 1
    assert result.stop_reason == "tool_limit" and result.final_response is None


def test_final_answer_allowed_at_budget_boundary():
    result = app.run_tool_use("Status of ORD-1001", max_tool_calls=1)
    assert result.stop_reason == "completed" and len(result.tool_history) == 1


def test_error_observation_can_be_used_to_correct_arguments():
    def decide(query, history):
        if not history:
            return app.Decision(tool_call=app.ToolCall("bad", "lookup_order", {}))
        if len(history) == 1:
            assert history[-1].status == "error"
            return app.Decision(tool_call=app.ToolCall("fixed", "lookup_order", {"order_id": "ORD-1001"}))
        return app.Decision(final_response=history[-1].output["status"])
    result = app.run_tool_use("ticket", decider=decide, max_tool_calls=2)
    assert [step.status for step in result.tool_history] == ["error", "success"]
    assert result.final_response == "shipped"


def test_duplicate_call_id_never_executes_twice(monkeypatch):
    executions = []
    monkeypatch.setitem(app.TOOLS, "lookup_order", lambda **args: executions.append(args) or {})
    with pytest.raises(ValueError, match="Duplicate"):
        app.run_tool_use("ticket", decider=lambda *_: app.Decision(
            tool_call=app.ToolCall("same", "lookup_order", {"order_id": "ORD-1001"})))
    assert len(executions) == 1


@pytest.mark.parametrize("decision", [None, app.Decision(), app.Decision(final_response=""),
    app.Decision(final_response=42), app.Decision(tool_call="bad"),
    app.Decision(tool_call=app.ToolCall("", "calculate", {})),
    app.Decision(tool_call=app.ToolCall("a", "", {})),
    app.Decision(tool_call=app.ToolCall("a", "calculate", {}), final_response="answer")])
def test_invalid_decision_fails_explicitly(decision):
    with pytest.raises(ValueError):
        app.run_tool_use("ticket", decider=lambda *_: decision)


@pytest.mark.parametrize("budget", [-1, 6, True, 1.5, "3"])
def test_invalid_budget_validated_before_decider(budget):
    with pytest.raises(ValueError, match="max_tool_calls"):
        app.run_tool_use("ticket", max_tool_calls=budget,
                         decider=lambda *_: pytest.fail("must validate first"))


@pytest.mark.parametrize("query", [None, "", " "])
def test_empty_query_rejected(query):
    with pytest.raises(ValueError, match="non-empty"):
        app.run_tool_use(query)


def test_decider_exception_propagates():
    def broken(*args):
        raise RuntimeError("unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        app.run_tool_use("ticket", decider=broken)
