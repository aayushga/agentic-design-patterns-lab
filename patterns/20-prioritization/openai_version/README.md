# Optional OpenAI Prioritization

The host computes eligible tasks first. An OpenAI model can rank that exact set
using task titles, host score components, deadlines, effort, and the remaining
work budget. It cannot add a task, bypass a prerequisite/resource/budget constraint,
modify task facts, claim completion, or execute an action. The result is a single
recommendation, not a persistent agent or automatic task runner.

## Setup

Python 3.10+, from the repository root:

```bash
python -m pip install -r patterns/20-prioritization/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
# Free preview: local rules, no key/SDK/request required.
python patterns/20-prioritization/openai_version/openai_prioritization.py --max-model-requests 0
```

`.env.example` lists the variables. The script reads exported environment variables;
it does not automatically load `.env` files. Never commit a real API key.
The SDK installation is separate from the free local implementation.

The next command **makes at most one billable model request**:

```bash
python patterns/20-prioritization/openai_version/openai_prioritization.py
```

Or call `run_openai_prioritization(...)` with your own validated backlog and current
snapshot. The model is explicit Python `model=`, then `OPENAI_MODEL`, then
`gpt-6-astra`. Overrides must support Responses, low reasoning effort, and strict
structured outputs. Missing credentials produce a clear error when an eligible
ranking needs a model request. Empty/completed/blocked backlogs and a zero model
budget need neither credentials nor the SDK.

## What the result means

A hypothetical valid model response might put release notes first:

```json
{
  "model": "gpt-6-astra",
  "model_attempts": 1,
  "decision": {
    "status": "selected",
    "selected_task_id": "notes",
    "ranking_source": "openai",
    "reason_code": "validated_model_ranking"
  }
}
```

This is an illustrative excerpt, not a live result. The full output includes the
ranked eligible records and unavailable IDs/reasons. The model may retain the
rule order or choose another valid order. `rule_score` remains a host-computed
baseline diagnostic even when model ordering differs; it is not an explanation
of the model's private reasoning. A valid order is not proof of optimality or
better prioritization quality.

The request contains only eligible task records; blocked/completed task text is
withheld. Task titles are untrusted data. The strict schema lists current eligible
IDs, and host code additionally requires each ID exactly once. A model response
that includes the blocked `fix` task, duplicates an ID, omits one, adds fields,
refuses, or produces invalid JSON is rejected. No model-provided task completion
or budget change is applied.

Fallbacks retain the original rule ranking and explicitly report:

- `ranking_source=rules_fallback`, `reason_code=invalid_model_ranking` for invalid output.
- `ranking_source=rules_fallback`, `reason_code=generation_not_completed` for incomplete generation.
- `ranking_source=rules_fallback`, `reason_code=provider_error` for SDK failure.

No raw provider exception or invalid model text is printed. The recommendation
may still contain caller-supplied task titles; use fictional data for learning.
The caller must re-evaluate a fresh snapshot before any later real execution,
because resources, completion state, and budget may have changed.

The official OpenAI SDK uses the Responses API with strict JSON, low reasoning
effort, `store=False`, a 1,500 output-token cap, a 30-second SDK timeout, and automatic
SDK retries disabled. `max_model_requests` accepts only 0 or 1; there are no retry,
repair, or execution calls. The client closes on success and failure. Inputs,
outputs, reasoning, and failed attempts may be billable. The request/output caps
are not dollar caps; `budget_minutes` controls fictional task effort only and does
not limit model spend. Token usage/cost are not estimated by this example.

Every committed test is offline with a fake SDK and no real API key. They check
request construction and host behavior, not live model quality or account access.
See the [parent guide](../README.md) for scoring, simulation, and scheduling limits.

Reference: [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
