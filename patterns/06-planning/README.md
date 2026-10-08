# Pattern 06: Planning

Planning turns a goal and constraints into an explicit sequence of steps **before
execution**. The executor checks that plan, runs the steps in dependency order,
and can ask for a revised plan when an observation changes what is possible.

**Goal + constraints → plan → validate → execute → observe → finish or replan**

This original exercise follows Chapter 6 of Antonio Gulli's *Agentic Design
Patterns*. It prepares a fictional team offsite proposal using a small venue and
catering catalog. No reservation, payment, live availability check, or message
is performed. A completed proposal always has `booked=False`.

## How it differs from earlier patterns

Tool Use chooses the next function and receives its observation. Planning first
lays out the whole proposed sequence, including dependencies and selected options,
then executes it. An unexpected failure can cause a new plan. Reflection improves
a draft through critique; here, execution observations change the plan's choices.

The local planner searches a small catalog for the cheapest combination satisfying
capacity and budget. The optional OpenAI planner generates the explicit plan.
Both use the same local validation and simulated execution.

This is deliberately bounded: the action vocabulary has two checks and one proposal
step. The goal is an offsite description, not a general task-programming language.
The selection changes with constraints; this is not a general-purpose planner,
calendar system, or Deep Research implementation. For an already-known workflow,
a fixed sequence may be simpler than model-generated planning.

## Free local run

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/06-planning/app.py
python patterns/06-planning/examples/basic_example.py
python patterns/06-planning/examples/advanced_example.py
```

No API key, SDK, network, or API charges are involved. The catalog contains:

| Venue | Capacity | Cost (USD) |
| --- | --- | --- |
| Cedar Room | 25 | 300 |
| City Loft | 30 | 400 |
| Garden Studio | 15 | 200 |

Catering is sandwich lunch at 10 USD per person or buffet lunch at 20 USD per
person. Prices are fictional whole-USD amounts; totals cover venue and catering
only, with no tax, transport, or other expenses modelled.

## Basic example

For 20 attendees and a 600 USD budget, the initial plan is:

```text
Goal: Prepare a team offsite proposal
Constraints: 20 attendees; 600 USD budget
Plan: Lowest-cost feasible catalog combination: 500 USD.
- venue: check_venue(cedar); depends on []
- catering: check_catering(sandwiches); depends on []
- proposal: build_proposal(None); depends on ['venue', 'catering']
Execution:
- venue: success
- catering: success
- proposal: success
```

The final proposal selects Cedar Room and sandwich lunch, costing 500 USD with
100 USD remaining. It is labelled simulated data and explicitly not booked.

## Advanced example

The advanced demo runs three separate cases:

1. **Unexpected unavailability:** Cedar Room is selected, but its check fails.
   The failure becomes a new constraint. The planner excludes `cedar`, chooses
   City Loft, and completes a 600 USD proposal after one replan.
2. **Impossible budget:** with 20 attendees and 450 USD, no catalog combination
   fits. The result is `no_feasible_plan`, with no executed steps or proposal.
3. **No replanning budget:** the venue check fails and `max_replans=0` prevents
   another plan. The result is `replan_limit`; no complete proposal is returned.

With 10 attendees, the local planner instead selects Garden Studio. With 30,
it needs City Loft and a sufficiently large budget. Choices depend on constraints.

## Function and result

Import using `importlib.import_module("patterns.06-planning.app")` from the
repository root, then call:

```python
result = module.run_planning(
    "Prepare a team offsite proposal",
    attendees=20,
    budget=600,
    max_replans=1,
    unavailable_venues=("cedar",),
)
```

| Result field | Meaning |
| --- | --- |
| `request` | Original goal, attendees, and budget |
| `status` | `completed`, `no_feasible_plan`, or `replan_limit` |
| `replans` | Plans requested after the initial plan |
| `proposal` | Complete proposal, or `None` if unsuccessful |
| `attempts` | Each plan, status, and execution observations |

The default allows one replan; valid limits are zero through two. Each nonempty
plan has exactly three steps. Execution stops at the first unavailable option,
records the failure, and excludes that option before replanning. Runtime
unavailability is deliberately hidden from the initial planner to demonstrate
adaptation. Completed checks are repeated on replanning because they have no
side effects. A real booking system would require a different recovery strategy.

## Plan validation

Before any execution, the complete plan is checked for unique IDs, allowed
actions, one occurrence of each action, known and non-excluded options, adequate
venue capacity, budget compliance, and dependencies on earlier steps. The
proposal must come last and depend on both checks. Either check can come first.

An empty plan is accepted only when a local catalog search confirms infeasibility.
Unknown options, invalid dependencies, over-budget plans, and contradictory
infeasibility claims fail explicitly. Planner errors also propagate rather than
being reported as success. The local planner minimizes cost over this finite
catalog; a valid OpenAI plan is not guaranteed to be the cheapest.

## Optional OpenAI version and offline tests

[OpenAI setup and costs](openai_version/README.md). OpenAI produces the structured
plan; Python validates and executes it. A runtime failure can trigger a second
planning request with the newly excluded option. Default model: `gpt-6-astra`.

```bash
python -m pip install -r patterns/06-planning/requirements.txt
python -m pytest patterns/06-planning/tests -q
```

Tests cover changing constraints, dependencies, failures, replanning, limits,
invalid plans, SDK request construction, and client cleanup. They use fake SDK
responses and block network connections, requiring no key or real SDK.
