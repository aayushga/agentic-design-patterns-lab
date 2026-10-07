# Optional OpenAI Planning

This version uses the official OpenAI Python SDK and Responses API to generate
an explicit offsite plan with [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).
Python validates that plan and executes its allowed actions against fictional
venue and catering data. If a check discovers an unavailable option, a bounded
replanning request excludes it.

The model creates a plan rather than issuing one tool call per turn. There are
no built-in search tools, live bookings, payments, or generated-code execution.
The [free local version](../README.md) needs no API key or model calls.

## Setup and run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/06-planning/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/06-planning/openai_version/openai_planning.py
```

The key entry above uses macOS's default zsh. Never commit an API key.
`.env.example` contains placeholders; exported environment variables are read
directly, without automatically loading `.env` files.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides it; the Python function's `model=` argument takes precedence over both.
The chosen model must support Responses, structured outputs, and low reasoning
effort, and be available to your account.

The CLI asks for a goal description and uses the demo constraints of 20 attendees
and 600 USD. Its complete output includes the request, plans, execution trace,
status, and proposal. CLI execution exits with a message when no proposal is
completed. Every successful proposal is simulated and has `booked=False`.

## Call from Python

```python
import importlib
from dataclasses import asdict

module = importlib.import_module(
    "patterns.06-planning.openai_version.openai_planning"
)
# This call makes live, billable model requests.
result = module.run_openai_planning(
    "Prepare a team offsite proposal",
    attendees=20,
    budget=600,
    unavailable_venues=("cedar",),
    max_replans=1,
)
print(asdict(result))
```

The `unavailable_venues` and `unavailable_catering` options simulate failures
found during execution, not facts initially visible to the planner. Each
subsequent request receives the catalog, original constraints, and options
excluded by earlier execution failures. No real availability is checked.

## Costs, limits, and validation

By default, the initial plan uses one billable model request, and one replan is
permitted: **at most two model requests**. `max_replans` accepts zero through two,
so the absolute maximum is three requests. Execution uses local Python only.
Even an infeasible request may consume one model request.

Each SDK request has a 30-second timeout, and automatic retries are disabled.
One client is reused and closes on success or failure. Total run time may span
multiple requests. Missing keys, API failures, incomplete responses, empty
text/refusals, and malformed plans fail explicitly.

A strict JSON schema defines a reason and a list of steps, each with `step_id`,
`action`, `option`, and `depends_on`. The local validator checks semantics too:
capacity, total cost, catalog IDs, exclusions, unique IDs, allowed actions, and
valid dependencies. It rejects the entire invalid plan before any step runs.
It also verifies a model's claim that no feasible catalog combination exists.

Instructions treat the goal and catalog as data and restrict planning to this
specific offsite domain. This is not a guarantee against prompt injection or
incorrect planning. Validity does not prove cost optimality or real-world
feasibility. The bounded catalog and local checks are the demo's execution
boundary; there is no arbitrary code dispatch or external action.

## Offline tests

Install the local pattern requirements, then run:

```bash
python -m pytest patterns/06-planning/tests -q
```

Tests substitute a fake SDK and block network connections. They incur no API
charges and require neither a key nor the real SDK. They validate orchestration
and request construction, not live model quality, account access, or latency.
