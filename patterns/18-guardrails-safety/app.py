"""Layered guards around a fictional, read-only order-status assistant."""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from types import MappingProxyType
from typing import Callable
import unicodedata

MAX_QUERY_CHARS = 1000
ORDER_ID = re.compile(r"ORD-[0-9]{3}")
PII_PATTERNS = (
    (re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I), "[REDACTED_EMAIL]"),
    (re.compile(r"(?<![0-9])[0-9]{3}-[0-9]{2}-[0-9]{4}(?![0-9])"), "[REDACTED_SSN]"),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), "[REDACTED_KEY]"),
)
INJECTION = re.compile(
    r"\b(?:ignore|disregard)\b.{0,40}\b(?:instructions|rules)\b"
    r"|\breveal\b.{0,40}\bsystem prompt\b|\bbypass\b.{0,20}\bguardrails\b", re.I | re.S,
)


@dataclass(frozen=True)
class Session:
    """Trusted caller identity supplied by the host, not by user/model fields."""
    customer_id: str

    def __post_init__(self):
        if not isinstance(self.customer_id, str) or not re.fullmatch(r"C-[0-9]{3}", self.customer_id):
            raise ValueError("Invalid demo customer identity")


@dataclass(frozen=True)
class Order:
    order_id: str
    owner_id: str
    status: str
    estimated_delivery: str | None


DEMO_SESSION = Session("C-100")
ORDERS = MappingProxyType({
    "ORD-101": Order("ORD-101", "C-100", "shipped", "2026-11-03"),
    "ORD-102": Order("ORD-102", "C-100", "processing", None),
    "ORD-202": Order("ORD-202", "C-200", "delivered", "2026-10-20"),
})


@dataclass(frozen=True)
class GuardEvent:
    stage: str
    decision: str
    code: str


@dataclass(frozen=True)
class GuardResult:
    status: str
    reply: str
    data: dict | None
    redacted_query: str | None
    redactions: int
    proposal_attempts: int
    tool_attempts: int
    audit: tuple[GuardEvent, ...]


class MissingAPIKey(Exception):
    """A configuration signal; no private exception text is returned."""


class InvalidProposal(ValueError):
    pass


Proposer = Callable[[str, str], object]
ReadTool = Callable[[Order], object]


def redact(text: str) -> tuple[str, int]:
    count = 0
    for pattern, replacement in PII_PATTERNS:
        text, matches = pattern.subn(replacement, text)
        count += matches
    return text, count


def local_proposer(query: str, order_id: str) -> dict:
    text = query.casefold()
    action = "request_refund" if "refund" in text else "lookup_order" if any(
        word in text for word in ("order", "delivery", "shipping", "status")
    ) else "unknown"
    return {"action": action, "order_id": order_id}


def validate_proposal(value: object, requested_order_id: str) -> str:
    if not isinstance(value, dict) or len(value) != 2 or set(value) != {"action", "order_id"}:
        raise InvalidProposal()
    if value["action"] not in ("lookup_order", "request_refund", "unknown"):
        raise InvalidProposal()
    if value["order_id"] != requested_order_id:
        raise InvalidProposal()
    return value["action"]


def read_order(order: Order) -> dict:
    return {"order_id": order.order_id, "status": order.status,
            "estimated_delivery": order.estimated_delivery}


def validate_snapshot(value: object, authorized_order: Order) -> dict:
    """Publish only the authorized record's exact, allowlisted public fields."""
    if not isinstance(value, dict) or len(value) != 3 or set(value) != {"order_id", "status", "estimated_delivery"}:
        raise ValueError("Invalid output fields")
    if (not isinstance(value["order_id"], str) or len(value["order_id"]) != 7
            or not isinstance(value["status"], str) or not 1 <= len(value["status"]) <= 12
            or (value["estimated_delivery"] is not None and
                (not isinstance(value["estimated_delivery"], str) or len(value["estimated_delivery"]) != 10))):
        raise ValueError("Invalid output size or type")
    if value != read_order(authorized_order):
        raise ValueError("Output does not match authorized snapshot")
    return dict(value)


def run_guarded_support(query: str, order_id: str = "ORD-101", *, session: Session | None = DEMO_SESSION,
                        proposer: Proposer = local_proposer, tool: ReadTool = read_order) -> GuardResult:
    audit: list[GuardEvent] = []
    sanitized = None
    redactions = proposal_attempts = tool_attempts = 0

    def event(stage, decision, code):
        audit.append(GuardEvent(stage, decision, code))

    def finish(status, reply, data=None):
        return GuardResult(status, reply, data, sanitized, redactions,
                           proposal_attempts, tool_attempts, tuple(audit))

    if not isinstance(session, Session):
        event("identity", "blocked", "authenticated_context_required")
        return finish("blocked", "An authenticated customer context is required.")
    event("identity", "passed", "host_context")
    if (not isinstance(query, str) or not 1 <= len(query) <= MAX_QUERY_CHARS or not query.strip()
            or not isinstance(order_id, str) or ORDER_ID.fullmatch(order_id) is None):
        event("input", "blocked", "invalid_input")
        return finish("blocked", "Provide a query of at most 1000 characters and an order ID such as ORD-101.")
    normalized = unicodedata.normalize("NFKC", query)
    if len(normalized) > MAX_QUERY_CHARS or any(ord(c) < 32 and c not in "\n\t" for c in normalized):
        event("input", "blocked", "invalid_normalized_input")
        return finish("blocked", "The query contains unsupported size or control characters.")
    sanitized, redactions = redact(normalized)
    if len(sanitized) > MAX_QUERY_CHARS:
        sanitized = None
        event("input", "blocked", "redacted_input_too_long")
        return finish("blocked", "Shorten the query and omit personal information.")
    event("input", "redacted" if redactions else "passed", "sensitive_patterns_removed" if redactions else "size_and_format")
    if INJECTION.search(sanitized):
        event("input", "blocked", "instruction_override_pattern")
        return finish("blocked", "This request matches an instruction-override pattern. Please ask a direct order-status question.")
    order = ORDERS.get(order_id)
    if order is None or order.owner_id != session.customer_id:
        event("authorization", "blocked", "order_not_accessible")
        return finish("blocked", "That order is not accessible in this customer context.")
    event("authorization", "passed", "order_owner_matches")
    proposal_attempts += 1
    try:
        action = validate_proposal(proposer(sanitized, order_id), order_id)
    except MissingAPIKey:
        event("proposal", "unavailable", "missing_api_key")
        return finish("unavailable", "Missing OPENAI_API_KEY. Export it before running the optional model version.")
    except (InvalidProposal, ValueError, TypeError):
        event("proposal", "blocked", "invalid_or_unbound_proposal")
        return finish("blocked", "The proposed action failed validation; no tool was called.")
    except Exception:
        event("proposal", "unavailable", "proposer_failed")
        return finish("unavailable", "The action proposer is unavailable; no tool was called.")
    event("proposal", "passed", "schema_and_order_binding")
    if action == "request_refund":
        event("action", "human_review", "write_action_not_available")
        return finish("human_review", "Refund requests require human billing review. No request was submitted or refund issued.")
    if action != "lookup_order":
        event("action", "blocked", "outside_order_status_scope")
        return finish("blocked", "This demo supports order-status lookups only.")
    event("action", "passed", "read_only_lookup")
    tool_attempts += 1
    try:
        payload = tool(order)
    except Exception:
        event("tool", "unavailable", "lookup_failed")
        return finish("unavailable", "The order lookup is unavailable. No account action was taken.")
    event("tool", "completed", "read_attempt_finished")
    try:
        data = validate_snapshot(payload, order)
    except Exception:
        event("output", "blocked", "invalid_or_ungrounded_snapshot")
        return finish("blocked", "The lookup response failed output checks; no order details were released.")
    event("output", "passed", "public_fields_match_authorized_snapshot")
    estimate = data["estimated_delivery"] or "not yet available"
    reply = f"Demo order {data['order_id']} is {data['status']}. Delivery estimate: {estimate}. No account changes were made."
    return finish("completed", reply, data)


def demo() -> None:
    print("Free fictional demo; host checks control a read-only lookup.")
    print(json.dumps(asdict(run_guarded_support("What is my order status? My email is alex@example.test.")), indent=2))


if __name__ == "__main__":
    demo()
