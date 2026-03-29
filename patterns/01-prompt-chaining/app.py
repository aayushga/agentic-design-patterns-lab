"""Prompt Chaining demo implemented with local Python functions.

This module simulates an LLM workflow without requiring API keys or network access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class ChainResult:
    """Container for prompt chaining outputs."""

    summary: str
    themes: List[str]
    final_response: Dict[str, object]


def summarize_text(text: str, max_words: int = 24) -> str:
    """Create a short summary by truncating to a word budget.

    This is a local stand-in for an LLM summarization step.
    """
    cleaned = " ".join(text.strip().split())
    words = cleaned.split()
    if not words:
        return ""
    if len(words) <= max_words:
        return cleaned
    return " ".join(words[:max_words]) + "..."


def extract_key_themes(summary: str) -> List[str]:
    """Extract key themes using simple keyword matching.

    This deterministic logic keeps the example easy to run and test.
    """
    theme_keywords = {
        "automation": ["automate", "automation", "workflow", "orchestrate"],
        "quality": ["quality", "reliable", "consistency", "accurate"],
        "speed": ["fast", "faster", "latency", "quick"],
        "cost": ["cost", "budget", "efficient", "efficiency"],
        "collaboration": ["team", "collaboration", "stakeholder", "handoff"],
    }

    lowered = summary.lower()
    themes: List[str] = []

    for theme, keywords in theme_keywords.items():
        if any(keyword in lowered for keyword in keywords):
            themes.append(theme)

    if not themes:
        themes.append("general")

    return themes


def generate_structured_response(original_text: str, summary: str, themes: List[str]) -> Dict[str, object]:
    """Generate a final structured response object."""
    return {
        "input_length": len(original_text),
        "summary": summary,
        "themes": themes,
        "recommended_next_step": (
            "Validate extracted themes with a domain expert and refine prompts for weak areas."
        ),
    }


def run_prompt_chain(text: str) -> ChainResult:
    """Run the full 3-step prompt chaining workflow."""
    summary = summarize_text(text)
    themes = extract_key_themes(summary)
    final_response = generate_structured_response(text, summary, themes)
    return ChainResult(summary=summary, themes=themes, final_response=final_response)


def main() -> None:
    """Run a local demo from the command line."""
    sample_input = (
        "Our product team wants to automate repetitive support workflows while improving quality and "
        "reducing response latency. We also need better collaboration across engineering and operations."
    )

    result = run_prompt_chain(sample_input)

    print("=== Prompt Chaining Demo ===")
    print(f"Summary: {result.summary}")
    print(f"Themes: {', '.join(result.themes)}")
    print("Final Response:")
    for key, value in result.final_response.items():
        print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
