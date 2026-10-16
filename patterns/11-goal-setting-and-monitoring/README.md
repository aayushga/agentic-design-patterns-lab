# Pattern 11: Goal Setting and Monitoring

Give an agent a specific objective, measurable success criteria, and a budget.
Observe what its actions actually change, then adapt or stop. This original
exercise follows Chapter 11 of Antonio Gulli's *Agentic Design Patterns*.

**Define goal → observe → choose action → act → measure → adapt or stop**

The task is to triage a fixed set of fictional support tickets within six action
attempts and 30 seconds. Triage means marking a ticket as reviewed in this
in-memory simulation. It does not mean resolving the customer's issue.

## What the monitor checks

| Element | Concrete implementation |
| --- | --- |
| Specific objective | Triage every ticket ID in `Goal.required_ticket_ids` |
| Completion measure | Number triaged / number required, plus pending IDs |
| Operational context | Count of high-priority tickets still pending |
| Progress signal | Remaining work: one triage action per pending ticket, plus one context-collection action where needed |
| Action budget | At most `max_steps` actions; blocked/no-change attempts also count |
| Stall budget | Stop after `max_stalled_steps` consecutive actions without reducing remaining work |
| Time budget | Monotonic elapsed time checked before/after action selection and after actions |

The goal cannot silently shrink, and the actor cannot declare its own success.
The Python monitor calculates completion from ticket state. `completed_fraction`
is a fraction of tickets triaged, not model confidence. Collecting missing
context reduces remaining work and resets the stall counter, while leaving
completion unchanged until triage succeeds.

`collect_context` reads only seeded fictional context. If it is unavailable,
the action reports blocked; requesting details does not magically produce them.
`triage` requires context. The deterministic actor prefers high-priority tickets.
Priority preference is a strategy, not an additional success criterion.

## Free local run

Python 3.10+; local code uses only the standard library. From the repository root:

```bash
python patterns/11-goal-setting-and-monitoring/app.py
python patterns/11-goal-setting-and-monitoring/examples/basic_example.py
python patterns/11-goal-setting-and-monitoring/examples/advanced_example.py
```

No SDK, API key, internet connection, or API charge is needed for these demos.
`app.py` prints a structured JSON result with the fixed goal, final progress,
action/observation history, stop reason, final simulated state, and data source.

### Basic example

All three tickets already have context:

```text
Goal: triage 3 required demo tickets
Budget: 6 actions, 30 seconds
Step 1: triage(T-101) -> success | triaged 1/3 | high-priority pending 1
Step 2: triage(T-102) -> success | triaged 2/3 | high-priority pending 0
Step 3: triage(T-103) -> success | triaged 3/3 | high-priority pending 0
Result: completed — All required tickets were triaged within the budgets.
Pending: []
Simulated data only; no API call, message, or real ticket update.
```

### Advanced example

The first action deliberately attempts triage without context. Observation of
that failure leads to a different action, then completion:

```text
Step 1: triage(T-101) -> blocked | triaged 0/3 | high-priority pending 2
Step 2: collect_context(T-101) -> success | triaged 0/3 | high-priority pending 2
Step 3: triage(T-101) -> success | triaged 1/3 | high-priority pending 1
Step 4: triage(T-102) -> success | triaged 2/3 | high-priority pending 0
Step 5: triage(T-103) -> success | triaged 3/3 | high-priority pending 0
Result: completed — All required tickets were triaged within the budgets.
```

The same example then runs separate unavailable-context and one-step-budget
scenarios. They finish as `stalled` and `step_limit`, retaining pending tickets.
The deadline path is checked with a fake clock in tests, so no sleeping is needed.

## Results and limits

- `completed`: every required ticket was triaged within the run budgets (or
  was already triaged, requiring no action).
- `stalled`: consecutive attempts produced no useful progress; the result asks
  for human input but sends no notification or message.
- `step_limit`: the action budget ended with required tickets pending.
- `deadline_exceeded`: the time budget expired. Even if the final action finished
  triage late, this is not reported as on-time completion; observed state is retained.

Deadline enforcement is cooperative. A blocking callback cannot be forcibly
interrupted by the loop; I/O integrations need their own timeout as well. State
is immutable input plus new in-memory snapshots, with no persistence or background
monitoring. Unrecognized actions, out-of-goal targets, malformed input, and actor
failures raise errors instead of fabricating successful outcomes. A failed run
does not modify input objects or real tickets.

## Relation to earlier patterns

Planning (06) constructs and revises a sequence. This example chooses the next
action from current state and measures whether a fixed objective is being met.
Reflection (04) critiques and revises an artifact; this monitor uses explicit
environment state and numeric completion criteria. Learning (09) updates a policy
from feedback; this example changes actions during one run without learning weights
or persisting a strategy. Pattern 19 later addresses broader system evaluation
and operational monitoring.

The book's coding example uses an LLM to generate code and judge its own success.
This simplified exercise uses a ticket simulator and independently calculated
metrics, illustrating the chapter's caution about trusting self-assessment.

## Optional OpenAI version and tests

See [OpenAI setup](openai_version/README.md). Astra chooses one action per request;
the same local simulator and monitor retain control of state and success.

```bash
python -m pip install -r patterns/11-goal-setting-and-monitoring/requirements.txt
python -m pytest patterns/11-goal-setting-and-monitoring/tests -q
```

Tests cover observed progress, adaptation, immutable goals/state, target scope,
stalls, budget boundaries, cooperative deadlines, invalid model output, API failure,
request construction, and client cleanup. Model responses are faked and network
connections are blocked. Tests need neither the OpenAI SDK nor an API key.
