"""Routing demo implemented with local Python logic.

This module provides a beginner-friendly, no-API implementation of a simple
intent router for billing, support, sales, and fallback requests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List


@dataclass
class RoutingResult:
    """Container for routing outputs."""

    intent: str
    route: str
    response: str


Handler = Callable[[str], str]


def detect_intent(user_input: str) -> str:
    """Detect intent using deterministic keyword matching.

    The goal is clarity and predictability for educational use.
    """
    lowered = user_input.lower()

    intent_keywords = {
        "billing": ["bill", "billing", "invoice", "payment", "refund", "charge"],
        "support": ["error", "bug", "issue", "help", "support", "broken", "crash"],
        "sales": ["buy", "price", "pricing", "plan", "demo", "purchase", "upgrade"],
    }

    for intent, keywords in intent_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            return intent

    return "unknown"


def handle_billing(user_input: str) -> str:
    """Handle billing-related requests."""
    return (
        "Billing team: I can help with invoices, charges, refunds, and payment status. "
        f"(received: {user_input})"
    )


def handle_support(user_input: str) -> str:
    """Handle technical support requests."""
    return (
        "Support team: I can help troubleshoot product issues and next steps. "
        f"(received: {user_input})"
    )


def handle_sales(user_input: str) -> str:
    """Handle sales-related requests."""
    return (
        "Sales team: I can help with pricing, plans, demos, and upgrades. "
        f"(received: {user_input})"
    )


def handle_fallback(user_input: str) -> str:
    """Handle requests that do not match known intents."""
    return (
        "General desk: I could not confidently classify this request. "
        "Please provide more context so I can route it correctly. "
        f"(received: {user_input})"
    )


def route_input(user_input: str) -> RoutingResult:
    """Route user input to the best handler and return structured output."""
    intent = detect_intent(user_input)

    handlers: Dict[str, Handler] = {
        "billing": handle_billing,
        "support": handle_support,
        "sales": handle_sales,
        "unknown": handle_fallback,
    }

    selected_handler = handlers.get(intent, handle_fallback)
    route = intent if intent in handlers else "unknown"
    response = selected_handler(user_input)

    return RoutingResult(intent=intent, route=route, response=response)


def demo_messages() -> List[str]:
    """Provide sample messages for local demo usage."""
    return [
        "I need a refund for a duplicate payment.",
        "The app crashes when I try to upload a file.",
        "Can you show pricing for the enterprise plan?",
        "What are your office hours?",
    ]


def main() -> None:
    """Run a local command-line demonstration of routing behavior."""
    print("=== Routing Demo ===")
    for message in demo_messages():
        result = route_input(message)
        print(f"\nInput: {message}")
        print(f"Intent: {result.intent}")
        print(f"Route: {result.route}")
        print(f"Response: {result.response}")


if __name__ == "__main__":
    main()
