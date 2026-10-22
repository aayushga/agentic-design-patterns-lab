# Optional OpenAI Exploration and Discovery

The model selects the next experiment from the host's current affordable frontier.
Python runs a fictional simulator and records its measured result. Model text is
never treated as experimental evidence, executable code, or a real-world finding.

## Setup

Python 3.10+, from the repository root:

```bash
python -m pip install -r patterns/21-exploration-discovery/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
# Free preview: no model calls, key, or SDK needed.
python patterns/21-exploration-discovery/openai_version/openai_discovery.py --max-model-requests 0
```

The free preview completes the same local discovery loop and labels model-disabled
choices as local rules. `.env.example` lists supported variables; scripts read
exported variables, not `.env` automatically. Never commit real credentials.

The next command **can make billable API calls**:

```bash
python patterns/21-exploration-discovery/openai_version/openai_discovery.py
```

The model is explicit Python `model=`, then `OPENAI_MODEL`, then `gpt-6-astra`.
Overrides must support Responses, low reasoning effort, and strict structured
outputs. A missing key or optional SDK gives a clear setup error when a model
proposal is first needed. The baseline has one candidate and runs without a model;
so do later decisions with only one affordable candidate. Zero experiments, no
available experimental cost, or reaching the target before any choice also needs
no model request or credentials.

## What is sent and accepted

Each request contains the target, current affordable/unattempted candidate IDs and
settings, their declared simulated costs and heuristic diagnostics, and previous
host-recorded evidence including fixed failure codes. It does not contain a table
of future outcomes. Candidate parent latency is already measured evidence, not
the candidate's predicted latency.

The strict response schema is just:

```json
{"config_id": "cfg-03"}
```

That ID is illustrative: it is accepted only if offered in that exact snapshot.
The host rejects tested, unoffered, unknown, and unaffordable IDs, extra fields,
invalid JSON, or incomplete output. An accepted ID causes one host-side simulated
experiment; it cannot set latency, alter budgets, generate code, or perform an
external action. Policy callbacks/evidence passed within Python are trusted code;
these restrictions apply to the model's response, not arbitrary injected Python.

Full CLI output contains `model`, `model_attempts`, and a structured `report` with
trials, selection sources, observed metrics, costs, stop reason, and unresolved
settings. Predictions/order can vary; no live model result is claimed here.
The report's latency values describe the fixed fictional simulator, not the model
API's response time or real pipeline performance.

## Request limits and fallback

`--max-model-requests` accepts 0–3 (default 3), independently of
`--max-experiments` (default 6) and `--cost-budget` (default 8). Single-candidate
steps do not consume model requests. After the model budget ends, experiments may
continue using local rules within the remaining experimental budgets.

| Selection source / reason | Meaning |
| --- | --- |
| `proposal / validated_proposal` | A model-selected ID passed host checks |
| `rules / only_candidate` | No model choice was needed |
| `rules / model_disabled` | Explicit zero model request budget |
| `rules / model_budget_exhausted` | Request allowance used; local selection continues |
| `rules_fallback / invalid_output` | Invalid/unoffered choice rejected; local selection used |
| `rules_fallback / generation_not_completed` | Incomplete model generation rejected |
| `rules_fallback / provider_error` | SDK failure; local selection used |
| `rules / model_stopped` | A previous model failure disabled further model calls |

Any SDK failure, invalid output, or incomplete response disables future model
requests for the run. There are no correction calls or SDK retries. A model error
is not a failed experiment: the locally selected configuration still runs and
must produce valid evidence. A simulator failure is recorded separately, spends
its experimental cost, and supplies no latency.

The official OpenAI SDK uses Responses with low reasoning effort, strict JSON,
`store=False`, a 1,000 output-token cap per attempt, and a 30-second SDK timeout.
Each request's client closes on success/failure. Timeouts are not a hard whole-run
deadline. Inputs, outputs, reasoning, and failed API attempts may be billable.
Request/output limits are not dollar caps; fictional cost units do not measure or
limit API spend. This example does not estimate token usage or monetary cost.

All committed tests use fake SDK responses, no real credentials, and blocked
network connections. They verify host behavior/request construction, not live
model quality, account access, or research validity. See the [parent guide](../README.md)
for the finite lab, deterministic evidence, and limits on discovery claims.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
