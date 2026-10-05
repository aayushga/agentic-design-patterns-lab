"""Optional OpenAI-backed Prompt Chaining implementation.

This module mirrors the local deterministic demo, but uses OpenAI model calls
for each chain step:
1) summarize input text
2) extract key themes
3) generate final structured response
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, List

if TYPE_CHECKING:
    from openai import OpenAI

DEFAULT_MODEL = "gpt-6-astra"


@dataclass
class OpenAIChainResult:
    """Container for OpenAI prompt chain outputs."""

    summary: str
    themes: List[str]
    final_response: Dict[str, Any]


def _get_client() -> OpenAI:
    """Create an OpenAI client from OPENAI_API_KEY."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise EnvironmentError(
            "OPENAI_API_KEY is not set. Add it to your environment before running this script."
        )
    from openai import OpenAI

    return OpenAI(api_key=api_key)


def _run_step(client: OpenAI, model: str | None, system_prompt: str, user_prompt: str) -> str:
    """Run one Responses API step and return plain text output."""
    response = client.responses.create(
        model=model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL,
        reasoning={"effort": "low"},
        input=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    if getattr(response, "status", "completed") != "completed":
        raise RuntimeError("OpenAI did not complete the chain step. Please retry.")
    content = response.output_text
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("OpenAI returned no text for the chain step (possibly a refusal).")
    return content.strip()


def summarize_text(client: OpenAI, text: str, model: str | None = None) -> str:
    """Step 1: summarize the raw input text."""
    return _run_step(
        client,
        model,
        "You create concise, accurate summaries.",
        (
            "Summarize the following text in 2-3 sentences. Focus on the most important points.\n\n"
            f"Text:\n{text}"
        ),
    )


def extract_key_themes(client: OpenAI, summary: str, model: str | None = None) -> List[str]:
    """Step 2: extract key themes from the summary."""
    raw = _run_step(
        client,
        model,
        "You extract themes from text with high precision.",
        (
            "Extract 3-6 key themes from the summary below. "
            "Return ONLY a JSON array of short theme strings.\n\n"
            f"Summary:\n{summary}"
        ),
    )

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, list) and parsed and all(
            isinstance(item, str) and item.strip() for item in parsed
        ):
            return [item.strip() for item in parsed]
    except json.JSONDecodeError:
        pass

    # Invalid JSON must not masquerade as extracted themes.
    return ["general"]


def generate_structured_response(
    client: OpenAI,
    original_text: str,
    summary: str,
    themes: List[str],
    model: str | None = None,
) -> Dict[str, Any]:
    """Step 3: produce final structured response JSON."""
    raw = _run_step(
        client,
        model,
        "You produce structured responses in valid JSON.",
        (
            "Using the original text, summary, and themes, return ONLY valid JSON with keys: "
            "input_length, summary, themes, recommended_next_step.\n\n"
            f"Original text:\n{original_text}\n\n"
            f"Summary:\n{summary}\n\n"
            f"Themes:\n{themes}"
        ),
    )

    try:
        parsed = json.loads(raw)
        if isinstance(parsed, dict):
            next_step = parsed.get("recommended_next_step")
            if isinstance(next_step, str) and next_step.strip():
                return {
                    "input_length": len(original_text),
                    "summary": summary,
                    "themes": themes,
                    "recommended_next_step": next_step.strip(),
                }
    except json.JSONDecodeError:
        pass

    # Fallback keeps the flow usable even when formatting drifts.
    return {
        "input_length": len(original_text),
        "summary": summary,
        "themes": themes,
        "recommended_next_step": "Review the summary and themes before taking action.",
    }


def run_prompt_chain(text: str, model: str | None = None) -> OpenAIChainResult:
    """Run the full OpenAI-backed prompt chaining workflow."""
    if not text.strip():
        raise ValueError("Please provide non-empty text.")
    client = _get_client()
    summary = summarize_text(client, text, model=model)
    themes = extract_key_themes(client, summary, model=model)
    final_response = generate_structured_response(client, text, summary, themes, model=model)
    return OpenAIChainResult(summary=summary, themes=themes, final_response=final_response)


def main() -> None:
    """Example CLI entrypoint."""
    sample_text = (
        "Our support organization needs to improve response quality, reduce handling time, "
        "and standardize escalation handoffs across teams."
    )

    try:
        result = run_prompt_chain(sample_text)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"Configuration/input error: {exc}") from None
    except Exception:
        raise SystemExit("OpenAI chain failed. Check model access, connectivity, and API limits.") from None

    print("=== OpenAI Prompt Chaining Demo ===")
    print("Summary:", result.summary)
    print("Themes:", result.themes)
    print("Final Response:", result.final_response)


if __name__ == "__main__":
    main()
