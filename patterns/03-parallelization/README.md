# Pattern 03: Parallelization

Parallelization runs independent tasks concurrently, then combines their results.
This example analyzes one support ticket in three ways: summary, keywords, and
urgency. Each task receives the original ticket and does not need the others' output.

Inspired by Chapter 3 of Antonio Gulli's *Agentic Design Patterns*. This is an
original, simplified implementation using Python's standard library.

## Workflow

```text
                       +--> Summary  ----+
Original support ticket+--> Keywords ----+--> Combine completed results
                       +--> Urgency  ----+
```

- Prompt Chaining: step A's output feeds step B, then step C.
- Routing: choose one appropriate handler for the request.
- Parallelization: run A, B, and C independently, then join their results.

The merge is a dependent step: it waits until each branch succeeds, fails, or times out.

## Why and When to Use It

Concurrency helps when tasks spend time waiting for independent I/O operations,
such as model requests, database lookups, or external services. Use it for multiple
analyses of the same input, independent research sources, or independent validation checks.

With three independent 150 ms waits, sequential execution takes roughly 450 ms;
concurrent execution takes roughly 150 ms plus overhead. This demo simulates those
waits with `asyncio.sleep`. The timing is illustrative and varies by machine.

`asyncio` overlaps waiting on a single event loop. It does not make CPU-heavy Python
work execute on multiple cores. The local analysis is intentionally simple: word
truncation, keyword counting, and an urgency heuristic. Concurrency does not improve
the accuracy of those heuristics or guarantee that a real API will respond faster.

## Run for Free

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/03-parallelization/app.py
python patterns/03-parallelization/examples/basic_example.py
python patterns/03-parallelization/examples/advanced_example.py
```

All three commands use local functions and simulated waiting time. They need no
API key, no SDK, and no network connection.

- `app.py`: full structured ticket analysis.
- `basic_example.py`: compare sequential and concurrent execution of the same tasks.
- `advanced_example.py`: simulate an account lookup timeout while retaining the other results.

## Example Output

For the local ticket “Urgent: checkout is down and paying customers are blocked.”,
the combined response looks like:

```text
summary: Urgent: checkout is down and paying customers are blocked.
keywords: urgent, checkout, down, paying, customers
urgency: high: explicit urgency or service interruption signal
```

The full structured result contains:

```json
{
  "original_query": "Urgent: checkout is down and paying customers are blocked.",
  "task_results": [
    {"task": "summary", "status": "success", "output": "Urgent: checkout is down and paying customers are blocked.", "error": null},
    {"task": "keywords", "status": "success", "output": "urgent, checkout, down, paying, customers", "error": null},
    {"task": "urgency", "status": "success", "output": "high: explicit urgency or service interruption signal", "error": null}
  ],
  "combined_response": "summary: Urgent: checkout is down and paying customers are blocked.\nkeywords: urgent, checkout, down, paying, customers\nurgency: high: explicit urgency or service interruption signal",
  "elapsed_seconds": 0.15
}
```

The elapsed value above is illustrative. Task results stay in the order they were
supplied, even when the tasks finish in a different order.

## Failure Handling and Limits

Each task has a timeout (5 seconds by default for local runs). A failed task has
`status: error`; an expired task has `status: timeout`. Both have `output: null`,
and the merge explicitly marks them unavailable. Successful results are preserved.
If all tasks fail, the combined response only reports unavailable analyses.

Caller cancellation propagates to the in-flight tasks. Blank input, an empty task
mapping, and nonpositive or nonfinite timeouts are rejected. Async analyzers must
cooperate with cancellation and avoid blocking the event loop; a timeout cannot
interrupt CPU work or a synchronous blocking call. Use a small set of independent
tasks; this demo has no queue or rate limiter for large workloads.

Concurrency can increase simultaneous API demand and does not reduce the number
of API requests. Choose limits appropriate for real services before scaling up.

## Offline Tests

From this pattern folder:

```bash
python -m pip install -r requirements.txt
python -m pytest
```

From the repository root, `python -m pytest` runs all patterns together. Tests use
async events to prove overlap and ordering instead of asserting a timing speedup.
They also cover failures, cancellation, timeouts, output validation, and the optional
OpenAI flow using a fake async SDK. Network connections are blocked by test fixtures.

## Optional OpenAI Version

See [the OpenAI setup guide](openai_version/README.md). It sends the three analyses
concurrently through the official async SDK, then merges results locally. The local
examples and all tests remain free of live API calls.
