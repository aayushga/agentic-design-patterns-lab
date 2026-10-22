# Pattern 21: Exploration and Discovery

Exploration gathers new evidence instead of repeatedly choosing what already looks
best. Discovery is the useful information learned from those experiments. This
example runs a bounded experiment loop in a fictional pipeline lab: measure a
baseline, propose an untested configuration, observe the outcome, and expand the
next experiment frontier using what was learned.

The research question is: **Can a combination of cache, batching, and compression
reach a target latency?** A candidate setting is a testable performance hypothesis;
only the host's experimental result becomes evidence. The policy balances trying
unseen setting values with exploring neighbors of promising observations.

Pattern 19 grades a fixed labeled set. This example chooses which unknown outcome
to measure next and changes its frontier after each observation. Pattern 20 ranks
known work items; here the value of an experiment is not known before it runs.

## Run for free

Python 3.10+; local examples use only the standard library. From the repository root:

```bash
python patterns/21-exploration-discovery/app.py
python patterns/21-exploration-discovery/examples/basic_example.py
python patterns/21-exploration-discovery/examples/advanced_example.py
python patterns/21-exploration-discovery/app.py --target-ms 40 --max-experiments 6 --cost-budget 8
```

There is no real pipeline, waiting, deployment, arbitrary code execution, or paid
API call. Latencies and cost units are deterministic fictional fixtures.

The **basic example** aims for latency ≤50 ms. Its output includes:

```text
1. cfg-00: cache=False, batch=1, compression=False -> 120ms; cost=1
2. cfg-01: cache=True, batch=1, compression=False -> 80ms; cost=1
3. cfg-03: cache=True, batch=4, compression=False -> 45ms; cost=2
Stop: target_met; target met: True
Best observed: cfg-03 at 45ms
Spent: 4 simulated cost units; remaining: 4
Attempted coverage: 37.5%; valid observations: 3
Untried: cfg-02, cfg-04, cfg-05, cfg-06, cfg-07
```

This excerpt omits selection-source fields for readability. The combined setting
was actually tested in the simulator. Three measurements do not establish a causal
interaction between cache/batching or prove that the result is globally optimal.
The other five configurations remain untested.

The **advanced example** requests a harder 40 ms target. It tries an additional
compression setting and encounters an unsupported combination:

```text
cfg-00 -> 120ms
cfg-01 -> 80ms
cfg-03 -> 45ms
cfg-07 -> FAILED (experiment_error); cost=2
cfg-05 -> 70ms
cfg-04 -> 110ms
Stop: experiment_limit; target met: False
Best observed: cfg-03 at 45ms
Spent: 8 simulated cost units; remaining: 0
Attempted coverage: 75.0%; valid observations: 5
Untried: cfg-02, cfg-06
Failed: cfg-07
```

The failed experiment still spends its reserved cost and attempt. It supplies no
latency measurement and is never retried in this run. The advanced script also
shows a separate two-unit cost limit and exhaustion of the entire finite lab.

## How the loop works

1. Start with only the baseline in the frontier.
2. Offer unattempted frontier configurations that fit the remaining cost budget.
3. Prefer configurations with more setting values absent from successful evidence;
   then prefer the lowest measured latency of a successful adjacent parent; break
   ties by configuration ID. An optional proposer may choose another offered ID.
4. Reserve cost and an attempt before running the simulator.
5. Validate the returned measurement, record success/failure, and update the best
   observed result. A successful observation adds three neighbors, each changing
   exactly one setting. Failed experiments do not expand the frontier.
6. Stop on the measured target, exhausted frontier, experiment cap, or cost limit.

This novelty heuristic is not statistical information gain, calibrated confidence,
or a learned model. Failed attempts do not count as successfully observed setting
values. A promising parent's result is a clue for selection, not a prediction of
its neighbor's unmeasured latency. All policies receive the same observed evidence;
they do not receive the simulator's future-outcome table.

| Budget / field | Meaning |
| --- | --- |
| `max_experiments` | 0–8 attempts; failures count |
| `cost_budget` | 0–16 fictional units; batch size 4 costs 2, otherwise 1 |
| `target_latency_ms` | Integer 1–10,000; checked against valid host measurements |
| `best_config_id`, `best_latency_ms` | Best valid observation so far; `null` when none exists |
| `attempted_coverage` | Unique attempted configurations / 8; failures are included |
| `successful_observations` | Valid measured results, excluding failed attempts |
| `untried_config_ids` | All unattempted lab settings, even those not yet in the frontier |
| `frontier_ids` | Discovered, unattempted neighbors; some may be unaffordable |

When several stopping conditions coincide, target success takes precedence, then
frontier exhaustion, then the experiment cap, then the cost cap. An exhausted
frontier does not mean every possible setting was measured: if the baseline fails,
its neighbors are never added. Failed IDs remain distinct from untried IDs.
The report records each configuration, selection source/reason, reserved cost,
validated measurement or fixed error code, and whether it established a new best.
Raw backend/proposer exceptions are omitted.

## Scope and limits

This is a small, finite teaching approximation of exploration. The eight allowed
configurations and deterministic lab truth are visible in source. Only their
outcomes are unknown to the selection policy before observation. It does not
create new dimensions of research, discover arbitrary unknown unknowns, search
the web, replicate a scientific multi-agent system, or establish a real performance
improvement. A more general system would generate and review new hypotheses,
expand its experiment space, repeat noisy measurements, and independently validate
findings. These fixtures provide no confidence intervals or evidence of real-world
novelty, generalization, or causal effects.

Each run starts fresh with in-memory evidence. Injected Python experiment/proposer
callbacks are trusted application code, not a sandbox for untrusted code. The model
version accepts only IDs; it cannot supply a measurement or an executable action.

## Optional model version and tests

[OpenAI exploration setup](openai_version/README.md) uses the official SDK to
propose up to three experiments from the current affordable frontier. Host code
validates the choice, runs the free lab, and records the evidence. Invalid output
or provider failure switches to local rules without further model requests.

```bash
python -m pip install -r patterns/21-exploration-discovery/requirements.txt
python -m pytest patterns/21-exploration-discovery/tests -q
```

Tests use fake SDK responses and blocked network access. They cover evidence-driven
frontier changes, novelty, proposal validation, unique attempts, cost accounting,
failed/invalid measurements, honest stop reasons, unknown results, model request
limits, fallback, and cleanup. They also run independently from this folder and
in GitHub Actions. No live OpenAI API call is required.

Inspired by Antonio Gulli's *Agentic Design Patterns*, Chapter 21.
This completes the repository's **21-pattern implementation sequence**.
