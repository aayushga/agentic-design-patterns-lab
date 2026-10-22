# Pattern 19: Evaluation and Monitoring

Evaluation asks whether an agent performs a defined task well. Monitoring records
observations over time and flags when measured behavior crosses an explicit limit.
This example evaluates the intent-routing task from Pattern 02, using a separate
host grader. It is useful when comparing prompt/model changes, enforcing a quality
gate, or finding failures that a convincing single demonstration could hide.

The flow is: **labeled cases → router → observations → metrics → gate/comparison → rolling alerts**.
The router receives only the query; case IDs and reference labels remain in the
host. No LLM judge is needed for an exact-match classification task.

## Run for free

Requires Python 3.10+; the local examples use only the standard library.
From the repository root:

```bash
python patterns/19-evaluation-monitoring/app.py
python patterns/19-evaluation-monitoring/examples/basic_example.py
python patterns/19-evaluation-monitoring/examples/advanced_example.py
python patterns/19-evaluation-monitoring/app.py --variant regressed --fail-on-gate
python patterns/19-evaluation-monitoring/app.py --output /tmp/evaluation-runs.jsonl
```

The fourth command deliberately exits with status 1: it demonstrates a failing
gate. Without `--fail-on-gate`, the CLI prints results and exits normally even
when a gate fails. No local example calls a paid service or sends notifications.

The **basic example** checks all eight synthetic cases against a keyword router.
It gets eight correct, 100% coverage, 100% accuracy, and no backend errors. Local
latency is measured with a monotonic clock and varies by machine. Token usage is
`null`/unknown because this router does not use an LLM.

The **advanced example** compares that baseline with an intentionally flawed
candidate: one technical query raises an error and one billing query is routed
to sales. It injects a clock to simulate 10 ms versus 250 ms latency without
sleeping. Representative output:

```text
baseline: accuracy=100%; errors=0.0%; p95=10.0ms
  Gate: {'passed': True, 'reasons': ()}
candidate: accuracy=75%; errors=12.5%; p95=250.0ms
  Gate: {'passed': False, 'reasons': ('low_accuracy', 'high_error_rate', 'high_p95_latency')}
Comparison: {"comparable": true, "accuracy_delta": -0.25, "p95_latency_delta_ms": 240.0, "reasons": ["accuracy_regression"]}
Rolling window after case04: ('low_accuracy', 'high_error_rate', 'high_p95_latency')
Rolling window after case08: ('low_accuracy', 'high_p95_latency')
Budget-limited run: 0.375 {'passed': False, 'reasons': ('insufficient_samples', 'incomplete_coverage')}
```

These delays and the regression are **simulated**, not model benchmarks.
The window keeps the last four attempted cases; the old error expires while a
wrong prediction still keeps accuracy low. Create a separate `RollingMonitor`
for each stream/variant; constructing a new one resets its in-memory history.
It provides reason codes to the caller, not a background alerting service.
Accuracy/error alerts here operate on already labeled evaluation observations;
unlabeled production traffic would need feedback or a separate quality evaluator.

## Metrics and decisions

| Field | Meaning |
| --- | --- |
| `coverage` | Attempted cases / all dataset cases |
| `accuracy` | Correct routes / attempted cases, including failures in the denominator |
| `task_success_rate` | Correct routes / all dataset cases, so skipped cases cannot disappear |
| `schema_valid_rate` | Valid route predictions / attempted cases |
| `error_rate` | Invalid outputs and backend failures / attempted cases; a valid wrong route is not a backend error |
| `p95_latency_ms` | Nearest-rank 95th percentile of all attempted-call elapsed times, including failures |
| `per_route` | Attempted count, correct count, and accuracy grouped by reference route |
| `known_input_tokens`, `known_output_tokens` | Sum of provider usage for calls with both valid counters; `null` if none are known |
| `usage_complete` | Whether all attempted calls have known usage; `null` when nothing was attempted |

Zero attempts yield unknown accuracy/error rate/latency, never perfect scores.
Local routers have unknown token counters. Partial known totals are labeled as
such; they are not complete billing estimates. Failed generations can consume tokens.
Provider output counts already include reasoning tokens; those are not added again.
This example does not calculate dollar cost or infer tokens from word counts.

Default gates require at least four attempted cases, 100% dataset coverage,
accuracy ≥90%, error rate ≤10%, and p95 latency ≤200 ms. Thresholds are illustrative
and configurable with `Thresholds` in Python; the latency gate is not a universal
model SLA. Treat these as local decisions, not proof of production readiness.

Comparisons require matching dataset fingerprints (including labels/order) and
complete coverage on both runs. Otherwise deltas are withheld. A candidate drop
greater than five percentage points raises `accuracy_regression`. Timing deltas
are withheld across measured/injected clock types; even within a type, use the
same controlled environment/workload for meaningful timing comparisons.

## Recorded observations

`--output` appends JSONL case records plus one summary record per run. Each includes
a schema version, run ID, UTC completion time, variant/model labels, timing source,
and dataset fingerprint. Query text, raw model output, and private exception text
are omitted. An error keeps its own case ID and a fixed error code; remaining
unattempted cases retain `not_run` and a reason. Logs are single-writer local files:
there is no locking, rotation, or crash-atomic append guarantee. Route labels and
metadata may still be sensitive; use fictional data and manage logs accordingly.

The checked-in dataset is bounded to 1–50 cases, 500 characters per query, and
64 KiB per input file. The eight examples are small, synthetic, and deliberately
suited to the baseline rules. They are **not** a representative benchmark, a held-out
quality estimate, or evidence of statistically significant drift. For real use,
curate independent cases, broaden coverage, review label quality, and repeat
measurements. This minimal classifier does not evaluate a full multi-step agent's
tool trajectory, semantic factuality, or safety; add task-specific evaluators for those.

## Optional model version and tests

[OpenAI evaluation setup](openai_version/README.md) replaces only the router with
the official SDK. It defaults to three requests, reports incomplete coverage, and
keeps grading/monitoring local. It is optional and incurs API charges only if run
with a valid API key. No OpenAI Evals/Graders service or observability vendor is required.

```bash
python -m pip install -r patterns/19-evaluation-monitoring/requirements.txt
python -m pytest patterns/19-evaluation-monitoring/tests -q
```

Tests use fake SDK responses and blocked network connections: no real API calls.
They cover denominators, invalid outputs, partial coverage, request limits, usage,
comparison validity, gates, rolling alerts, append-only logs, and CLI exit status.
The same tests run in GitHub Actions and independently from this pattern folder.

References: Antonio Gulli, *Agentic Design Patterns*, Chapter 19; and OpenAI's
[evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
Next: **Pattern 20 — Prioritization**.

Gates reject missing, non-finite, or inconsistent metric types with `invalid_metrics`.
Accuracy-drop comparisons allow only floating-point rounding noise at the configured
boundary; a drop exactly equal to the tolerance is not a regression.
