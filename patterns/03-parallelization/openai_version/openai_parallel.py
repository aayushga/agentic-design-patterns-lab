"""Optional concurrent OpenAI analyses, followed by a local merge.

Running this script makes up to three billable API requests. Local app.py and
all tests run without API access.
"""
from __future__ import annotations

import asyncio
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

if __package__:
    from ..app import ParallelResult, run_parallel_analysis
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import ParallelResult, run_parallel_analysis

DEFAULT_MODEL = "gpt-6-astra"
TASK_PROMPTS = {
    "summary": "Summarize this support ticket in one sentence. Use only the ticket's content.",
    "keywords": "Extract up to five useful keywords from this ticket. Return a comma-separated list.",
    "urgency": (
        "Assess this support ticket's urgency as high, medium, or low. "
        "Give one short reason grounded only in the ticket."
    ),
}


async def run_openai_parallel(
    text: str, model: str | None = None, *, task_timeout: float = 30.0
) -> ParallelResult:
    """Use one async client for three independent requests; merge locally."""
    if not text.strip():
        raise ValueError("Please provide a non-empty query")
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Missing OPENAI_API_KEY. Export it before running this example.")
    selected_model = model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL

    # Local examples and fake-SDK tests do not require the real package.
    from openai import AsyncOpenAI

    async with AsyncOpenAI(api_key=api_key, max_retries=0) as client:
        async def analyze(query: str, instruction: str) -> str:
            response = await client.responses.create(
                model=selected_model,
                reasoning={"effort": "low"},
                instructions=instruction,
                input=query,
            )
            if response.status != "completed":
                raise RuntimeError("The model did not complete this analysis")
            return response.output_text

        # Bind each instruction when creating its analyzer, avoiding late binding.
        def make_analyzer(instruction: str):
            async def analyzer(query: str) -> str:
                return await analyze(query, instruction)
            return analyzer

        tasks = {name: make_analyzer(prompt) for name, prompt in TASK_PROMPTS.items()}
        return await run_parallel_analysis(text, analyzers=tasks, task_timeout=task_timeout)


def main() -> None:
    print("Optional OpenAI demo: up to three billable requests; no automatic retries.")
    query = input("Enter a support ticket: ").strip()
    try:
        result = asyncio.run(run_openai_parallel(query))
    except ValueError as exc:
        raise SystemExit(f"Configuration/input error: {exc}") from None
    except Exception:
        raise SystemExit("Could not start OpenAI analysis. Check SDK installation and configuration.") from None
    print(json.dumps(asdict(result), indent=2))
    if any(task.status != "success" for task in result.task_results):
        raise SystemExit("Some analyses were unavailable; successful results are shown above.")


if __name__ == "__main__":
    main()
