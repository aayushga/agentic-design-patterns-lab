"""Advanced Routing example with decision explanation and structured output."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict, List

# Allow running example directly without packaging setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import detect_intent


@dataclass
class AdvancedRoutingResult:
    """Container for advanced routing outputs."""

    input_text: str
    selected_route: str
    route_reason: str
    output: Dict[str, object]


def explain_route_choice(user_input: str, intent: str) -> str:
    """Explain why a route was selected using transparent keyword evidence."""
    lowered = user_input.lower()
    evidence: Dict[str, List[str]] = {
        "billing": ["billing", "invoice", "payment", "refund", "charge"],
        "support": ["error", "bug", "issue", "help", "broken", "crash"],
        "sales": ["buy", "price", "pricing", "plan", "demo", "upgrade"],
    }

    if intent == "unknown":
        return "No clear billing/support/sales keywords were found, so fallback routing was selected."

    matched_keywords = [token for token in evidence[intent] if token in lowered]
    if not matched_keywords:
        return f"Route '{intent}' selected based on overall phrasing match."

    return (
        f"Route '{intent}' selected because these keywords were detected: "
        + ", ".join(matched_keywords)
    )


def build_structured_output(user_input: str, route: str, reason: str) -> Dict[str, object]:
    """Build a predictable structured output for downstream systems."""
    return {
        "request": user_input,
        "classification": {
            "route": route,
            "confidence": "high" if route != "unknown" else "low",
        },
        "explanation": reason,
        "next_action": (
            f"Dispatch to '{route}' queue" if route != "unknown" else "Ask user for clarification"
        ),
    }


def run_advanced_router(user_input: str) -> AdvancedRoutingResult:
    """Detect intent, explain route selection, and return structured output."""
    intent = detect_intent(user_input)
    selected_route = intent if intent in {"billing", "support", "sales"} else "unknown"
    route_reason = explain_route_choice(user_input, selected_route)
    output = build_structured_output(user_input, selected_route, route_reason)
    return AdvancedRoutingResult(
        input_text=user_input,
        selected_route=selected_route,
        route_reason=route_reason,
        output=output,
    )


if __name__ == "__main__":
    query = "Can I get pricing details and a demo for your enterprise plan?"
    result = run_advanced_router(query)

    print("Input:", result.input_text)
    print("Selected route:", result.selected_route)
    print("Why this route:", result.route_reason)
    print("Structured output:", result.output)
