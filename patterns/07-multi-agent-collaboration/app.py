"""Multi-Agent Collaboration: supervisor, specialists, and an explicit writer handoff.

The free version simulates role agents with deterministic Python functions.
No API calls, account checks, refunds, repairs, or messages are performed.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
import re
from typing import Callable

ROLE_KEYWORDS = {
    "billing": ("charged", "billing", "invoice", "payment", "refund", "subscription"),
    "technical": ("crash", "error", "upload", "login", "bug", "slow", "broken"),
}
ROLE_ASSESSMENTS = {
    "billing": "Billing issue reported; transaction records have not been checked.",
    "technical": "Technical issue reported; root cause has not been verified.",
}
ROLE_NEXT_STEPS = {
    "billing": "Please share the relevant invoice number so billing can investigate.",
    "technical": "Please share the error message and app version so technical support can investigate.",
}


@dataclass
class Assignment:
    roles: list[str]
    reason: str


@dataclass
class Finding:
    evidence: str
    assessment: str
    next_step: str


@dataclass
class Handoff:
    sender: str
    recipient: str
    status: str
    findings: list[Finding]
    error: str | None = None


@dataclass
class CollaborationResult:
    original_query: str
    assignment: Assignment
    status: str
    final_response: str | None
    handoffs: list[Handoff]
    writer_error: str | None = None


Supervisor = Callable[[str], Assignment]
Specialist = Callable[[str], list[Finding]]
Writer = Callable[[str, list[Handoff]], str]


def local_supervisor(query: str) -> Assignment:
    """Select only the roles recognized by a small, transparent keyword rule."""
    lowered = query.lower()
    roles = [role for role, words in ROLE_KEYWORDS.items() if any(word in lowered for word in words)]
    reason = "Recognized " + " and ".join(roles) + " concerns." if roles else "No supported concern recognized."
    return Assignment(roles, reason)


def _local_findings(query: str, role: str) -> list[Finding]:
    sentences = re.split(r"(?<=[.!?])\s+", query.strip())
    evidence = next((sentence for sentence in sentences
                     if any(word in sentence.lower() for word in ROLE_KEYWORDS[role])), query.strip())
    return [Finding(evidence, ROLE_ASSESSMENTS[role], ROLE_NEXT_STEPS[role])]


def billing_specialist(query: str) -> list[Finding]:
    return _local_findings(query, "billing")


def technical_specialist(query: str) -> list[Finding]:
    return _local_findings(query, "technical")


def local_writer(query: str, handoffs: list[Handoff]) -> str:
    """Compose from specialist messages, including explicit unavailable work."""
    parts = ["Thank you for contacting support."]
    for message in handoffs:
        if message.status == "error":
            parts.append(f"The {message.sender} specialist's analysis is unavailable.")
        else:
            for finding in message.findings:
                parts.append(f'{message.sender.capitalize()} — you reported: "{finding.evidence}"')
                parts.extend([finding.assessment, finding.next_step])
    parts.append("No account changes or fixes have been performed.")
    return "\n".join(parts)


def validate_query(query: str) -> None:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Please provide a non-empty support query")


def _validate_assignment(assignment: Assignment) -> None:
    if (not isinstance(assignment, Assignment) or not isinstance(assignment.roles, list)
            or not all(isinstance(role, str) and role in ROLE_KEYWORDS for role in assignment.roles)
            or len(set(assignment.roles)) != len(assignment.roles)
            or not isinstance(assignment.reason, str) or not assignment.reason.strip()):
        raise ValueError("Supervisor must assign unique supported roles and provide a reason")


def _validate_findings(query: str, findings: list[Finding]) -> None:
    if not isinstance(findings, list) or not 1 <= len(findings) <= 3:
        raise ValueError("Specialist must return one to three findings")
    for finding in findings:
        if (not isinstance(finding, Finding)
                or not all(isinstance(value, str) and value.strip()
                           for value in (finding.evidence, finding.assessment, finding.next_step))
                or finding.evidence not in query):
            raise ValueError("Each finding needs an exact ticket excerpt, assessment, and next step")


def run_collaboration(query: str, *, supervisor: Supervisor = local_supervisor,
                      specialists: dict[str, Specialist] | None = None,
                      writer: Writer = local_writer) -> CollaborationResult:
    """Run each assigned specialist once, then deliver validated handoffs to the writer.

    The supervisor cannot introduce arbitrary roles. Specialist failures retain
    partial work; all-specialist or writer failure produces no final reply.
    """
    validate_query(query)
    agents = {"billing": billing_specialist, "technical": technical_specialist} if specialists is None else specialists
    if (not isinstance(agents, dict) or not set(agents) <= set(ROLE_KEYWORDS)
            or not all(callable(agent) for agent in agents.values())):
        raise ValueError("Specialists must be callable entries for supported roles")
    assignment = supervisor(query)
    _validate_assignment(assignment)
    if not assignment.roles:
        return CollaborationResult(query, assignment, "needs_clarification",
            "Please describe your billing or technical issue so the support team can help.", [])
    handoffs = []
    for role in assignment.roles:
        if role not in agents:
            handoffs.append(Handoff(role, "writer", "error", [], "Specialist is not configured"))
            continue
        try:
            findings = agents[role](query)
            _validate_findings(query, findings)
        except Exception:
            # Avoid copying arbitrary SDK error details or credentials into output.
            handoffs.append(Handoff(role, "writer", "error", [], "Specialist failed or returned invalid findings"))
        else:
            handoffs.append(Handoff(role, "writer", "success", deepcopy(findings)))
    if not any(message.status == "success" for message in handoffs):
        return CollaborationResult(query, assignment, "failed", None, handoffs)
    try:
        # Writers receive copies, preserving the inspection trace even if customized.
        reply = writer(query, deepcopy(handoffs))
        if not isinstance(reply, str) or not reply.strip():
            raise ValueError("Writer returned no usable text")
    except Exception:
        return CollaborationResult(query, assignment, "failed", None, handoffs,
                                   writer_error="Writer failed or returned no usable text")
    partial = any(message.status == "error" for message in handoffs)
    if partial:
        reply = "Some specialist work is unavailable; this reply needs human review.\n" + reply.strip()
    return CollaborationResult(query, assignment, "needs_review" if partial else "completed",
                               reply.strip(), handoffs)


def main() -> None:
    print(json.dumps(asdict(run_collaboration("I was charged twice. The app crashes during upload.")), indent=2))


if __name__ == "__main__":
    main()
