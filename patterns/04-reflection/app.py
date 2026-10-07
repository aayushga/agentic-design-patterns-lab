"""Reflection: draft, critique, revise, and recheck with a bounded feedback loop.

This local support-reply demo uses transparent rules, not an API or model.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
import re
from typing import Callable

MAX_REVISIONS = 5


@dataclass
class Critique:
    """Approval and actionable issues reported by the critic."""

    approved: bool
    issues: list[str]


@dataclass
class ReflectionStep:
    """A reviewed draft; revision zero is the initial draft."""

    revision: int
    draft: str
    critique: Critique


@dataclass
class ReflectionResult:
    """Retain the reviewed drafts and an explicit stopping condition."""

    original_query: str
    initial_draft: str
    final_draft: str
    approved: bool
    revisions: int
    stop_reason: str
    history: list[ReflectionStep]


Producer = Callable[[str], str]
Reviewer = Callable[[str, str], Critique]
Reviser = Callable[[str, str, Critique], str]

ACKNOWLEDGEMENT = "Thank you for contacting support."
NEXT_STEP = "Please share the relevant invoice number or error message so we can investigate."


def generate_draft(query: str) -> str:
    """Start with an intentionally incomplete reply to make reflection visible."""
    return "We received your request."


def critique_draft(query: str, draft: str) -> Critique:
    """Check a narrow, educational rubric; this is not factual verification."""
    issues = []
    lowered = draft.lower()
    if "thank you" not in lowered:
        issues.append("acknowledgement: add a courteous acknowledgement")
    if " ".join(query.lower().split()) not in " ".join(lowered.split()):
        issues.append("request: mention the customer's original issue")
    if "please share" not in lowered:
        issues.append("next_step: ask for relevant details to investigate")
    if len(draft.split()) > 80:
        issues.append("length: keep the reply within 80 words")
    # Quoted customer reports are data, not promises made by the reply.
    claims = lowered.replace(f'you reported: "{query.lower()}"', "")
    if re.search(r"\b(guaranteed|guarantee|resolved|approved)\b", claims):
        issues.append("promises: remove unsupported resolution or approval claims")
    return Critique(approved=not issues, issues=issues)


def revise_draft(query: str, draft: str, critique: Critique) -> str:
    """Apply the critic's named findings using deterministic edits."""
    issue_names = {issue.split(":", 1)[0] for issue in critique.issues}
    if issue_names & {"length", "promises"}:
        # Rebuild from known request data rather than trying to patch a claim.
        return f'{ACKNOWLEDGEMENT} You reported: "{query}" {NEXT_STEP}'
    additions = []
    if "acknowledgement" in issue_names:
        additions.append(ACKNOWLEDGEMENT)
    additions.append(draft)
    if "request" in issue_names:
        additions.append(f'You reported: "{query}"')
    if "next_step" in issue_names:
        additions.append(NEXT_STEP)
    return " ".join(additions)


def validate_inputs(query: str, max_revisions: int, initial_draft: str | None) -> None:
    """Reject invalid configuration before any producer or API call."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("Please provide a non-empty query")
    if type(max_revisions) is not int or not 0 <= max_revisions <= MAX_REVISIONS:
        raise ValueError(f"max_revisions must be an integer between 0 and {MAX_REVISIONS}")
    if initial_draft is not None and (not isinstance(initial_draft, str) or not initial_draft.strip()):
        raise ValueError("initial_draft must contain text")


def _validated_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Producer/reviser returned no usable text")
    return text.strip()


def _validate_critique(critique: Critique) -> None:
    """Malformed or contradictory feedback must not count as approval."""
    if not isinstance(critique, Critique) or type(critique.approved) is not bool:
        raise ValueError("Critic must return a Critique with a boolean approval")
    if not isinstance(critique.issues, list) or not all(
        isinstance(issue, str) and issue.strip() for issue in critique.issues
    ):
        raise ValueError("Critic issues must be a list of non-empty strings")
    if critique.approved != (not critique.issues):
        raise ValueError("Critic approval must agree with its issues")


def run_reflection(
    query: str,
    *,
    initial_draft: str | None = None,
    max_revisions: int = 2,
    producer: Producer = generate_draft,
    reviewer: Reviewer = critique_draft,
    reviser: Reviser = revise_draft,
) -> ReflectionResult:
    """Review every candidate before returning it, including the last revision.

    Stop on approval, the revision budget, or a repeated draft. Exceptions from
    a producer or critic propagate; they never become successful approval.
    """
    validate_inputs(query, max_revisions, initial_draft)
    draft = _validated_text(producer(query) if initial_draft is None else initial_draft)
    first_draft = draft
    history = []
    seen = set()
    revisions = 0

    while True:
        critique = reviewer(query, draft)
        _validate_critique(critique)
        history.append(ReflectionStep(revisions, draft, critique))
        seen.add(" ".join(draft.split()))
        if critique.approved:
            stop_reason = "approved"
            break
        if revisions >= max_revisions:
            stop_reason = "revision_limit"
            break
        candidate = _validated_text(reviser(query, draft, critique))
        if " ".join(candidate.split()) in seen:
            stop_reason = "no_progress"
            break
        draft = candidate
        revisions += 1

    return ReflectionResult(
        original_query=query,
        initial_draft=first_draft,
        final_draft=draft,
        approved=critique.approved,
        revisions=revisions,
        stop_reason=stop_reason,
        history=history,
    )


def main() -> None:
    query = "I was charged twice for my subscription."
    print(json.dumps(asdict(run_reflection(query)), indent=2))


if __name__ == "__main__":
    main()
