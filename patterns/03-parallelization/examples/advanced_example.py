"""Keep successful ticket analyses when one independent task times out."""
import asyncio
from dataclasses import asdict
import json
from pathlib import Path
import sys

if __package__:
    from ..app import default_analyzers, run_parallel_analysis
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import default_analyzers, run_parallel_analysis


async def slow_account_lookup(text: str) -> str:
    """Simulate an unavailable external service without contacting one."""
    await asyncio.sleep(2)
    return "Account lookup completed"


async def main() -> None:
    tasks = default_analyzers()
    tasks["account_lookup"] = slow_account_lookup
    query = "Urgent: checkout is down and paying customers are blocked."
    result = await run_parallel_analysis(query, analyzers=tasks, task_timeout=0.5)
    print("Simulated service timeout; successful analyses remain available.")
    print(json.dumps(asdict(result), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
