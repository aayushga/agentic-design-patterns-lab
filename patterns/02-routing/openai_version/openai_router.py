"""Optional OpenAI-backed router for Pattern 02: Routing.

This module keeps the same routing idea as the local implementation, but uses an
LLM to classify user intent into one of: billing, support, sales, or unknown.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import os
from typing import Callable, Dict


DEFAULT_MODEL = "gpt-6-astra"

ALLOWED_ROUTES = {"billing", "support", "sales", "unknown"}


@dataclass
class OpenAIRoutingResult:
    """Structured routing output for downstream consumers."""

    original_query: str
    selected_route: str
    confidence: str
    reason: str
    handler_response: str


Handler = Callable[[str], str]


def handle_billing(user_input: str) -> str:
    return (
        "Billing team: I can help with invoices, charges, refunds, and payment status. "
        f"(received: {user_input})"
    )


def handle_support(user_input: str) -> str:
    return (
        "Support team: I can help troubleshoot product issues and next steps. "
        f"(received: {user_input})"
    )


def handle_sales(user_input: str) -> str:
    return (
        "Sales team: I can help with pricing, plans, demos, and upgrades. "
        f"(received: {user_input})"
    )


def handle_unknown(user_input: str) -> str:
    return (
        "General desk: I could not confidently classify this request. "
        "Please provide more context so I can route it correctly. "
        f"(received: {user_input})"
    )


def _build_handlers() -> Dict[str, Handler]:
    return {
        "billing": handle_billing,
        "support": handle_support,
        "sales": handle_sales,
        "unknown": handle_unknown,
    }


def classify_intent_with_openai(user_input: str, model: str | None = None) -> Dict[str, str]:
    """Classify intent using OpenAI and return route metadata.

    Returns a dict with `route`, `confidence`, and `reason`.
    Raises ValueError if OPENAI_API_KEY is missing.
    """
    if not user_input.strip():
        raise ValueError("Please provide a non-empty request.")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError(
            "Missing OPENAI_API_KEY. Set it in your environment before running the OpenAI router."
        )

    # Lazy import so this module can still be imported in environments where
    # the OpenAI package is not installed and the OpenAI path is not used.
    from openai import OpenAI

    client = OpenAI(api_key=api_key)

    system_prompt = (
        "You are an intent router. Classify the user query into exactly one route: "
        "billing, support, sales, or unknown. Return strict JSON with keys: "
        "route, confidence, reason. Confidence must be one of: high, medium, low."
    )

    response = client.responses.create(
        model=model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_input},
        ],
        text={"format": {
            "type": "json_schema",
            "name": "intent_classification",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "route": {"type": "string", "enum": sorted(ALLOWED_ROUTES)},
                    "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
                    "reason": {"type": "string"},
                },
                "required": ["route", "confidence", "reason"],
                "additionalProperties": False,
            },
        }},
    )

    fallback = {
        "route": "unknown",
        "confidence": "low",
        "reason": "Model returned empty, malformed, or incomplete output; using 'unknown'.",
    }
    if getattr(response, "status", "completed") != "completed":
        return fallback
    try:
        parsed = json.loads(response.output_text)
    except (json.JSONDecodeError, TypeError):
        return fallback
    if not isinstance(parsed, dict):
        return fallback

    route = parsed.get("route")
    confidence = parsed.get("confidence")
    reason = parsed.get("reason")
    route = route.strip().lower() if isinstance(route, str) else ""
    confidence = confidence.strip().lower() if isinstance(confidence, str) else "low"
    reason = reason.strip() if isinstance(reason, str) else ""

    if route not in ALLOWED_ROUTES:
        return {
            "route": "unknown",
            "confidence": "low",
            "reason": "Model returned an invalid route; falling back to 'unknown'.",
        }
    if not reason:
        return fallback
    if confidence not in {"high", "medium", "low"} or route == "unknown":
        confidence = "low"

    return {"route": route, "confidence": confidence, "reason": reason}


def route_with_openai(user_input: str, model: str | None = None) -> OpenAIRoutingResult:
    """Classify route via OpenAI, dispatch to handler, and return structured output."""
    classification = classify_intent_with_openai(user_input, model=model)

    selected_route = classification["route"]
    handlers = _build_handlers()
    handler = handlers.get(selected_route, handle_unknown)

    return OpenAIRoutingResult(
        original_query=user_input,
        selected_route=selected_route,
        confidence=classification["confidence"],
        reason=classification["reason"],
        handler_response=handler(user_input),
    )


def main() -> None:
    """Small CLI demo for the OpenAI-backed router."""
    query = input("Enter a request to route: ").strip()
    if not query:
        print("Please provide a non-empty request.")
        return

    try:
        result = route_with_openai(query)
    except ValueError as exc:
        raise SystemExit(f"Configuration/input error: {exc}") from None
    except Exception:
        raise SystemExit("OpenAI routing failed. Check model access, connectivity, and API limits.") from None

    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
