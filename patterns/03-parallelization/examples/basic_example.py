"""Compare sequential and concurrent execution using the same local tasks."""
import asyncio
from pathlib import Path
import sys

if __package__:
    from ..app import run_parallel_analysis
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_parallel_analysis


async def main() -> None:
    query = "The app is down and our customers cannot complete checkout."
    sequential = await run_parallel_analysis(query, sequential=True)
    parallel = await run_parallel_analysis(query)
    print("Simulated I/O waits; no API calls.")
    print(f"Sequential: {sequential.elapsed_seconds:.3f}s")
    print(f"Concurrent: {parallel.elapsed_seconds:.3f}s")
    print("Combined response:")
    print(parallel.combined_response)


if __name__ == "__main__":
    asyncio.run(main())
