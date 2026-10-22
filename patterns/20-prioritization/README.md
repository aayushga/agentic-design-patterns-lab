# Pattern 20: Prioritization

Prioritization chooses **what to work on next** when several tasks compete for
limited time and resources. This example ranks a fictional release backlog using
importance, deadline urgency, waiting time, and prerequisite value. Host code first
excludes tasks that have not arrived, lack a resource, have unfinished dependencies,
or cannot fit the remaining work budget. After each simulated completion it
recomputes eligibility and scores.

Use this pattern for project backlogs, support queues, or selecting the next action
from an existing plan. Pattern 06 creates/validates a plan; this example selects
among existing tasks. Pattern 16 chooses a response profile within an inference
budget; this example allocates a simulated worker's task time.

## Run for free

Python 3.10+; the local examples use only the standard library. From the repository root:

```bash
python patterns/20-prioritization/app.py
python patterns/20-prioritization/examples/basic_example.py
python patterns/20-prioritization/examples/advanced_example.py
python patterns/20-prioritization/app.py --budget-minutes 10 --max-steps 2
```

All work is fictional: the simulator advances an integer minute counter, deducts
declared effort, and marks tasks complete in memory. It does not sleep, fix code,
contact customers, read a live queue, or perform real task actions. No API key or
paid service is needed.

The **basic example** starts with 25 work minutes. Collecting metrics has the best
eligible score and is a prerequisite for the checkout fix. Representative output:

```text
1. metrics: score=27, effort=5m (importance=16, urgency=9, aging=0, unlock=2)
2. notes: score=14, effort=8m (importance=8, urgency=6, aging=0, unlock=0)
3. feedback: score=4, effort=6m (importance=4, urgency=0, aging=0, unlock=0)
Deferred fix: dependencies_pending
Selected: metrics
SIMULATED 00-05m: Collect release metrics; budget left=20m
SIMULATED 05-17m: Fix checkout regression; budget left=8m
SIMULATED 17-25m: Write release notes; budget left=0m
Stop: no_eligible_tasks | Pending: feedback
```

The fix becomes eligible after metrics complete. Its score is recomputed rather
than preserving the original order. Feedback stays pending when the budget ends.

The **advanced example** adds an incident arriving at minute 5 and a dashboard task
whose reporting resource is unavailable. The arrival time is a predefined fixture,
not an external monitor. The selected order becomes:

```text
00-05m  metrics    -> unlocks the checkout fix
05-12m  incident   -> newly arrived urgent work outranks the fix
12-24m  fix        -> now 4 minutes late against its minute-20 deadline
24-30m  feedback   -> fits the 6-minute balance; notes need 8 minutes

Pending: dashboard (resource unavailable), notes (over budget)
Stop: no_eligible_tasks
One-step cap: step_limit | Next eligible: incident
```

The simulator reconsiders priorities between tasks. A task already started runs
to completion; it is not interrupted by an arrival mid-task. It does not advance
time automatically to wait for future arrivals when no task is eligible.

## Ranking and constraints

For eligible tasks the local rule is:

```text
rule_score = 4 × importance + 3 × urgency + aging + unlock_bonus
```

| Component | Definition |
| --- | --- |
| Importance | Host-supplied integer 1–5 |
| Urgency | 5 if due/overdue; 4 if due within 10 minutes; 3 within 30; 2 within 60; 1 later; 0 without a deadline |
| Aging | One point per 15 minutes since creation, capped at 5 |
| Unlock bonus | Two points per arrived, unfinished direct dependent, capped at 6 |
| Ties | Shorter declared effort first, then task ID alphabetically |

The unlock bonus rewards prerequisite value; a dependent with several prerequisites
may still be blocked after one completes. Aging is bounded and does not guarantee
freedom from starvation. These weights are a transparent teaching heuristic, not
an optimal scheduler or a guarantee of maximum completed value.

Dependencies, arrival time, resource presence, and remaining budget are **hard
eligibility constraints**. Deadlines are **soft priorities**: the example can start
a task that will finish late and reports `lateness_minutes` in each simulation
step (`null` for no deadline). It does not reserve future work time or prove
that a deadline is feasible. Work minutes are declared estimates, not measured
runtime and not an OpenAI token/dollar budget. Resources are trusted availability
labels, not real worker assignments, concurrency controls, or connected tools.

`prioritize(...)` returns the selected ID, ranking source, fixed reason code,
ranked eligible tasks with score components, and unavailable tasks with all current
blocking reasons. Completed tasks are omitted. `simulate(...)` returns steps,
completed/pending IDs, remaining budget, virtual time, and a final decision:

- `all_completed`: every backlog task is complete, including any supplied initial completions.
- `no_eligible_tasks`: pending work exists but is currently blocked; this is not success.
- `step_limit`: the explicit step cap was reached with eligible work still remaining.

Backlogs are bounded to 20 immutable task records, unique IDs, 160-character titles,
importance 1–5, and effort 1–120 minutes. Work budgets are 0–480 minutes; simulation
step caps are 0–20. Unknown dependencies, cycles, duplicate edges, invalid types,
and inconsistent initial completion state are rejected. Time values are
nonnegative integer offsets, not calendar dates. Host-supplied task facts and
completion state are trusted inputs, not extracted from task-title prose.
State is local and in memory; separate calls do not persist a work queue.

## Optional OpenAI version and tests

[OpenAI prioritization setup](openai_version/README.md) lets a model reorder the
current eligible set in one request. Python accepts only an exact permutation of
those IDs, retaining every host-owned task fact and constraint. Invalid/incomplete
responses or SDK failures use an explicit local-rule fallback. The model version
returns a recommendation for one snapshot and does not run tasks or a model loop.

```bash
python -m pip install -r patterns/20-prioritization/requirements.txt
python -m pytest patterns/20-prioritization/tests -q
```

Tests use fake SDK responses and blocked network connections. They cover graph and
state validity, changing deadlines/arrivals/resources, score explanations, hard
budget/dependency constraints, deterministic ties, simulated accounting/stopping,
model ranking validation, bounded requests, fallback, and client cleanup.
The tests also run independently from this folder and in GitHub Actions.

Inspired by Antonio Gulli's *Agentic Design Patterns*, Chapter 20. This is an
original simplified implementation rather than the book's LangChain task manager.
Next: **Pattern 21 — Exploration and Discovery**.
