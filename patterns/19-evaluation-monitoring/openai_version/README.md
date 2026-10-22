# Optional OpenAI Evaluation and Monitoring

Use an OpenAI intent router as the system under test. The host retains reference
labels, scores exact route matches, measures elapsed request time, reads available
SDK token usage, and applies the same local quality gates as the free version.

## Setup

Python 3.10+, from this repository root:

```bash
python -m pip install -r patterns/19-evaluation-monitoring/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
python patterns/19-evaluation-monitoring/openai_version/openai_evaluation.py --max-cases 0
```

The zero-request run needs neither a key nor the SDK: it reports zero coverage,
unknown accuracy/usage, and a failed gate. `.env.example` lists supported variables;
these scripts read exported variables and do not automatically load `.env` files.
Never commit a real key.

The following commands **make billable API requests**:

```bash
# Default budget: at most 3 sequential requests, so only 3/8 dataset coverage.
python patterns/19-evaluation-monitoring/openai_version/openai_evaluation.py
# Explicitly allow the entire eight-case dataset, and fail the command if a gate fails.
python patterns/19-evaluation-monitoring/openai_version/openai_evaluation.py --max-cases 8 --fail-on-gate --output /tmp/openai-evaluation.jsonl
```

The official OpenAI SDK calls the Responses API with strict route JSON, low
reasoning effort, `store=False`, a 1,000 output-token cap per attempt, a 30-second
SDK timeout, and automatic SDK retries disabled. The model is selected by explicit
Python `model=`, then `OPENAI_MODEL`, then `gpt-6-astra`. Overrides must support
Responses, low reasoning effort, and structured outputs. Query text is untrusted
input; no account actions or tools are executed.

Each case causes at most one application-level model attempt. The budget is 0–50
and clamped to the dataset size. An SDK exception marks the current case as an
error and stops further calls; remaining cases are `not_run`. An incomplete or
invalid model response is scored as an error, preserving available usage, then
the next distinct case may run within the same budget. There are no correction
calls. The request cap is not a dollar cap: inputs, outputs, reasoning, and failures
can be billable. SDK timeouts are not a hard overall run deadline.

## Read the result

A hypothetical default run with three correct predictions would show:

```json
{
  "attempted_count": 3,
  "coverage": 0.375,
  "accuracy": 1.0,
  "task_success_rate": 0.375,
  "gate": {"passed": false, "reasons": ["insufficient_samples", "incomplete_coverage"]}
}
```

This is an excerpt, not a live result. The full CLI also prints route-level scores,
latency, error rates, and token fields. Default runs cannot establish full-dataset
success and cannot be compared using `compare_reports`. Even a complete run may
fail the example's 200 ms p95 threshold; choose realistic thresholds in Python
for your use case. Measured latency includes request/SDK overhead, not just model
compute. Actual model predictions, latency, availability, and usage can vary.

Token counters come from response usage; missing counters remain unknown. Known
partial totals never stand in for complete cost. No fabricated usage, price
estimate, live API test, or model-quality claim is included. Optional JSONL output
omits raw queries/responses; see the parent guide for logging and dataset limits.

The eight synthetic examples are a teaching set, not a held-out benchmark. All
committed tests are offline and require no SDK installation or real credentials.
The implementation uses ordinary Responses calls, not OpenAI Evals/Graders APIs.

References: [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs),
[reasoning token accounting](https://developers.openai.com/api/docs/guides/reasoning),
and [evaluation best practices](https://developers.openai.com/api/docs/guides/evaluation-best-practices).
