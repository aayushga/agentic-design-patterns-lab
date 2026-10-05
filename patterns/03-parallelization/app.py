"""Run independent analyses concurrently, then combine their results.

The default analyzers use deterministic Python logic and simulated I/O waits.
No model, API key, or network access is required.
"""
from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import asdict, dataclass
import json
import math
import re
from time import perf_counter
from typing import Awaitable, Callable, Mapping

Analyzer = Callable[[str], Awaitable[str]]
DEMO_DELAY_SECONDS = 0.15


@dataclass
class TaskResult:
    """Record success, failure, or timeout for one independent task."""

    task: str
    status: str
    output: str | None = None
    error: str | None = None


@dataclass
class ParallelResult:
    """Keep branch outputs visible alongside the combined response."""

    original_query: str
    task_results: list[TaskResult]
    combined_response: str
    elapsed_seconds: float


async def summarize_ticket(text: str) -> str:
    """Truncate the ticket as a transparent stand-in for summarization."""
    await asyncio.sleep(DEMO_DELAY_SECONDS)
    words = text.split()
    return " ".join(words[:24]) + ("..." if len(words) > 24 else "")


async def extract_keywords(text: str) -> str:
    """Return frequent words, excluding a small set of stop words."""
    await asyncio.sleep(DEMO_DELAY_SECONDS)
    stop_words = {
        "a", "an", "and", "are", "as", "at", "be", "by", "can", "for", "from",
        "has", "have", "i", "in", "is", "it", "my", "of", "on", "our", "the",
        "this", "to", "we", "when", "with",
    }
    words = re.findall(r"[a-z]+", text.lower())
    counts = Counter(word for word in words if word not in stop_words)
    return ", ".join(word for word, _ in counts.most_common(5)) or "No keywords found"


async def assess_urgency(text: str) -> str:
    """Flag explicit urgency signals; this is an educational heuristic."""
    await asyncio.sleep(DEMO_DELAY_SECONDS)
    words = set(re.findall(r"[a-z]+", text.lower()))
    if words & {"urgent", "outage", "blocked", "critical", "down"}:
        return "high: explicit urgency or service interruption signal"
    return "normal: no explicit urgency signal detected"


def default_analyzers() -> dict[str, Analyzer]:
    """All three tasks receive the same original text, independently."""
    return {
        "summary": summarize_ticket,
        "keywords": extract_keywords,
        "urgency": assess_urgency,
    }


async def _run_task(name: str, analyzer: Analyzer, text: str, timeout: float) -> TaskResult:
    try:
        output = await asyncio.wait_for(analyzer(text), timeout=timeout)
        if not isinstance(output, str) or not output.strip():
            raise ValueError("Analyzer returned no usable text")
        return TaskResult(task=name, status="success", output=output.strip())
    except asyncio.TimeoutError:
        return TaskResult(task=name, status="timeout", error="Task exceeded its time limit")
    except Exception as exc:
        # Do not expose request contents or credentials in exception messages.
        return TaskResult(task=name, status="error", error=f"Task failed ({type(exc).__name__})")


def combine_results(results: list[TaskResult]) -> str:
    """Merge only completed results, explicitly showing unavailable analyses."""
    lines = []
    for result in results:
        if result.status == "success":
            lines.append(f"{result.task}: {result.output}")
        else:
            lines.append(f"{result.task}: unavailable ({result.status})")
    return "\n".join(lines)


async def run_parallel_analysis(
    text: str,
    *,
    analyzers: Mapping[str, Analyzer] | None = None,
    task_timeout: float = 5.0,
    sequential: bool = False,
) -> ParallelResult:
    """Run a small, explicitly supplied set of independent I/O tasks.

    `sequential=True` provides a comparison using the same tasks and input.
    Per-task failures do not discard other results. Cancellation propagates.
    """
    if not text.strip():
        raise ValueError("Please provide a non-empty query")
    if not math.isfinite(task_timeout) or task_timeout <= 0:
        raise ValueError("task_timeout must be a positive, finite number")
    tasks = dict(default_analyzers() if analyzers is None else analyzers)
    if not tasks:
        raise ValueError("Please provide at least one analyzer")

    started = perf_counter()
    if sequential:
        results = []
        for name, analyzer in tasks.items():
            results.append(await _run_task(name, analyzer, text, task_timeout))
    else:
        results = await asyncio.gather(
            *(_run_task(name, analyzer, text, task_timeout) for name, analyzer in tasks.items())
        )
    # gather preserves supplied task order even if tasks finish in a different order.
    combined = combine_results(results)
    return ParallelResult(text, results, combined, round(perf_counter() - started, 4))


def main() -> None:
    """Print the full free local demo result."""
    query = "Our checkout is down and customers are blocked from placing orders. Please help urgently."
    result = asyncio.run(run_parallel_analysis(query))
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    main()
