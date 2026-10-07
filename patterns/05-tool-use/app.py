"""Tool Use: choose a function, validate it, execute it, and observe the result.

The free local decider understands a small command grammar, not arbitrary prose.
Tools are read-only demo functions; no network, model, or code evaluation is used.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import math
import operator
import re
from typing import Callable

DEMO_ORDERS = {
    "ORD-1001": {"status": "shipped", "items_total": 120.0, "shipping_fee": 10.0, "currency": "USD"},
    "ORD-1002": {"status": "processing", "items_total": 45.0, "shipping_fee": 5.0, "currency": "USD"},
}
OPERATIONS = {"add": operator.add, "subtract": operator.sub,
              "multiply": operator.mul, "divide": operator.truediv}


@dataclass
class ToolCall:
    call_id: str
    name: str
    arguments: dict


@dataclass
class ToolObservation:
    call_id: str
    name: str
    arguments: dict
    status: str
    output: dict | None = None
    error: str | None = None


@dataclass
class Decision:
    """Exactly one next action: a tool call or a final answer."""
    tool_call: ToolCall | None = None
    final_response: str | None = None


@dataclass
class ToolUseResult:
    original_query: str
    final_response: str | None
    stop_reason: str
    tool_history: list[ToolObservation]


def lookup_order(order_id: str) -> dict:
    """Return a copy of a fictional order, never real customer data."""
    if not isinstance(order_id, str) or not re.fullmatch(r"ORD-\d{4}", order_id):
        raise ValueError("order_id must have the form ORD-1001")
    if order_id not in DEMO_ORDERS:
        raise ValueError(f"Demo order {order_id} was not found")
    return {"order_id": order_id, **DEMO_ORDERS[order_id], "source": "simulated demo data"}


def calculate(operation: str, left: float, right: float) -> dict:
    """Perform one named arithmetic operation; never evaluate code or expressions."""
    if not isinstance(operation, str) or operation not in OPERATIONS:
        raise ValueError("operation must be add, subtract, multiply, or divide")
    for value in (left, right):
        if type(value) not in (int, float) or not -1e12 <= value <= 1e12:
            raise ValueError("Operands must be finite numbers between -1e12 and 1e12")
    if operation == "divide" and right == 0:
        raise ValueError("Cannot divide by zero")
    value = OPERATIONS[operation](left, right)
    if not math.isfinite(value):
        raise ValueError("Calculation produced a non-finite result")
    return {"operation": operation, "left": left, "right": right, "value": value}


# Explicit dispatch is the execution boundary; model text cannot name arbitrary code.
TOOLS = {"lookup_order": lookup_order, "calculate": calculate}
TOOL_ARGUMENTS = {"lookup_order": {"order_id"}, "calculate": {"operation", "left", "right"}}


def execute_tool(call: ToolCall) -> ToolObservation:
    """Report unknown tools and invalid arguments as observations, not successes."""
    try:
        if call.name not in TOOLS:
            raise ValueError(f"Unknown tool: {call.name}")
        if not isinstance(call.arguments, dict) or set(call.arguments) != TOOL_ARGUMENTS[call.name]:
            raise ValueError(f"Arguments must contain exactly: {', '.join(sorted(TOOL_ARGUMENTS[call.name]))}")
        output = TOOLS[call.name](**call.arguments)
        return ToolObservation(call.call_id, call.name, call.arguments, "success", output=output)
    except ValueError as exc:
        return ToolObservation(call.call_id, call.name, call.arguments, "error", error=str(exc))


def local_decider(query: str, history: list[ToolObservation]) -> Decision:
    """Recognize order IDs and 'calculate A + B' (also -, *, /) for the demo."""
    if history:
        last = history[-1]
        if last.status == "error":
            return Decision(final_response=f"Unable to complete the request: {last.error}")
        data = last.output
        if last.name == "lookup_order":
            if "total" in query.lower():
                return Decision(tool_call=ToolCall("local-2", "calculate", {
                    "operation": "add", "left": data["items_total"], "right": data["shipping_fee"]}))
            return Decision(final_response=f"Demo order {data['order_id']} is {data['status']} (simulated data).")
        if len(history) > 1 and history[-2].name == "lookup_order":
            order = history[-2].output
            return Decision(final_response=f"Demo order {order['order_id']} total including shipping: {data['value']:.2f} {order['currency']} (simulated data).")
        return Decision(final_response=f"Calculation result: {data['value']:g}")

    order = re.search(r"\bORD-\d{4}\b", query.upper())
    if order:
        return Decision(tool_call=ToolCall("local-1", "lookup_order", {"order_id": order.group()}))
    number = r"(-?\d+(?:\.\d+)?)"
    expression = re.fullmatch(rf"\s*calculate\s+{number}\s*([+*/-])\s*{number}\s*", query, re.I)
    if expression:
        left, symbol, right = expression.groups()
        operation = {"+": "add", "-": "subtract", "*": "multiply", "/": "divide"}[symbol]
        return Decision(tool_call=ToolCall("local-1", "calculate", {
            "operation": operation, "left": float(left), "right": float(right)}))
    return Decision(final_response="Try 'status of ORD-1001', 'total for ORD-1001', or 'calculate 12 + 8'. Demo data only.")


Decider = Callable[[str, list[ToolObservation]], Decision]


def validate_inputs(query: str, max_tool_calls: int) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Please provide a non-empty query")
    if type(max_tool_calls) is not int or not 0 <= max_tool_calls <= 5:
        raise ValueError("max_tool_calls must be an integer between 0 and 5")


def run_tool_use(query: str, *, decider: Decider = local_decider,
                 max_tool_calls: int = 3) -> ToolUseResult:
    """Return observations to the decider until an answer or the call limit.

    Failed tool attempts count toward the budget. Decider/SDK failures propagate.
    Reusing a call ID is a protocol error; it never executes a second time.
    """
    validate_inputs(query, max_tool_calls)
    history = []
    seen_ids = set()
    while True:
        decision = decider(query, history)
        if not isinstance(decision, Decision) or (decision.tool_call is None) == (decision.final_response is None):
            raise ValueError("Decider must return exactly one tool call or final response")
        if decision.final_response is not None:
            if not isinstance(decision.final_response, str) or not decision.final_response.strip():
                raise ValueError("Final response must contain text")
            return ToolUseResult(query, decision.final_response.strip(), "completed", history)
        call = decision.tool_call
        if (not isinstance(call, ToolCall) or not isinstance(call.call_id, str)
                or not call.call_id.strip() or not isinstance(call.name, str) or not call.name.strip()):
            raise ValueError("Tool call requires a non-empty call ID and tool name")
        if call.call_id in seen_ids:
            raise ValueError("Duplicate tool call ID")
        if len(history) >= max_tool_calls:
            return ToolUseResult(query, None, "tool_limit", history)
        seen_ids.add(call.call_id)
        history.append(execute_tool(call))


def main() -> None:
    print(json.dumps(asdict(run_tool_use("What is the status of ORD-1001?")), indent=2))


if __name__ == "__main__":
    main()
