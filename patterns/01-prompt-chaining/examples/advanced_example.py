"""Advanced Prompt Chaining example with query refinement and intent detection."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import sys
from typing import Dict

# Allow running example directly without packaging setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@dataclass
class AdvancedChainResult:
    """Container for advanced chaining workflow outputs."""

    clarified_question: str
    intent: str
    response_blueprint: Dict[str, str]


def rewrite_for_clarity(question: str) -> str:
    """Normalize user wording into a clearer request."""
    cleaned = " ".join(question.strip().split())
    if cleaned and not cleaned.endswith("?"):
        cleaned += "?"
    return cleaned.capitalize()


def identify_intent(question: str) -> str:
    """Identify user intent with simple rule-based matching."""
    lowered = question.lower()
    if any(token in lowered for token in ["how", "steps", "guide"]):
        return "instruction"
    if any(token in lowered for token in ["compare", "difference", "vs"]):
        return "comparison"
    if any(token in lowered for token in ["recommend", "best", "should i"]):
        return "recommendation"
    return "general_question"


def build_final_response_structure(clarified_question: str, intent: str) -> Dict[str, str]:
    """Build a structured response template from prior chain steps."""
    return {
        "question": clarified_question,
        "intent": intent,
        "response_sections": "Context -> Key Points -> Actionable Next Steps",
        "tone": "clear, concise, and practical",
    }


def run_advanced_chain(question: str) -> AdvancedChainResult:
    """Run the advanced prompt chain: clarity -> intent -> structured response."""
    clarified_question = rewrite_for_clarity(question)
    intent = identify_intent(clarified_question)
    response_blueprint = build_final_response_structure(clarified_question, intent)
    return AdvancedChainResult(
        clarified_question=clarified_question,
        intent=intent,
        response_blueprint=response_blueprint,
    )


if __name__ == "__main__":
    user_question = "how can i improve response quality in a support chatbot"
    result = run_advanced_chain(user_question)

    print("Clarified question:", result.clarified_question)
    print("Intent:", result.intent)
    print("Response blueprint:", result.response_blueprint)
