# Pattern 16: Resource-Aware Optimization

A support-guidance agent chooses a response profile using the **remaining output-token
allowance, call count, and time**. It reuses exact cached answers, reserves resources
before attempting work, and can explicitly supply a brief response when a detailed
one will not fit. If the detailed profile is mandatory, it stops rather than
silently selecting the brief profile.

This is an original, simplified exercise inspired by Chapter 16 of Antonio Gulli's
*Agentic Design Patterns*. It focuses on admission control and conservative accounting;
it does not copy the book's ADK agents, web search, or critique implementation.

Pattern 02 routes by intent. Pattern 12 handles failures and retries. This pattern
asks **which response path can still fit**, including after earlier attempts have
consumed resources. Desired detail is supplied explicitly, rather than inferred by
another paid classification call or guessed from query length.

## Profiles and decisions

| Profile | Detail | Reserved output tokens | Optional model effort | Illustrative time forecast |
| --- | --- | ---: | --- | ---: |
| economy | brief | 600 | low | 1 second |
| thorough | detailed | 1600 | medium | 3 seconds |

Brief requests consider economy only. Detailed requests consider thorough first,
then economy if `allow_degraded=True`. The default session has an allowance of
2200 output tokens, two backend attempts, and ten seconds from agent construction.

```text
Validate work item → check session deadline → check exact session cache
  → choose an eligible profile → reserve output tokens and one call
  → run backend → validate answer → return and optionally cache
                           ↓ known transient failure
                  recheck remaining resources for economy
```

The local backend uses short, deterministic fictional support rules. It recognizes
login/password and invoice/billing keywords; other queries receive general support
guidance. These are canned demonstrations, not general question answering.
There are no model calls, actual generated-token measurements, sleeps, or account
actions in the local examples. Forecasts are illustrative, not benchmarked latency.

## Run for free

Python 3.10+; from the repository root:

```bash
python -m pip install -r patterns/16-resource-aware-optimization/requirements.txt
python patterns/16-resource-aware-optimization/app.py
python patterns/16-resource-aware-optimization/examples/basic_example.py
python patterns/16-resource-aware-optimization/examples/advanced_example.py
python -m pytest patterns/16-resource-aware-optimization/tests -q
```

The implementation uses only the Python standard library; pytest is needed for tests.
You can also run `python -m pytest` from this pattern folder. No OpenAI SDK, key,
network access, or billable call is needed to run the local examples or tests.

The basic example submits a brief login request and repeats it. Abridged output:

```text
First request
  status: answered
  selected_profile: economy
  calls_made: 1
  reserved_output_tokens: 600
  remaining_output_tokens: 0
  answer: Record the exact error and request support review. No account change is performed.

Repeated request
  status: cached
  cache_hit: true
  calls_made: 0
  reserved_output_tokens: 0
  session_calls: 1
  session_reserved_output_tokens: 600
```

The advanced example compares these outcomes:

```text
Enough resources: answered; profile=thorough; reserved=1600
Small token allowance: degraded; profile=economy; reserved=600
Detailed response required: blocked; profile=None; calls=0
Short time forecast: degraded; profile=economy; reserved=600
Preferred backend unavailable: degraded; profile=economy; calls=2; reserved=2200
Different request after allowance spent: blocked; profile=None; calls=0
```

`app.py` shows the full structured result, including query, requested detail, status,
selected profile, answer, cache flag, per-request and session accounting, elapsed
session seconds, and a decision trace. `degraded` means the requested detail was
not supplied; it does not mean the underlying support issue was resolved.

## Accounting and limits

- Every attempt reserves its full output cap **before** the backend runs. Reservations
  are never refunded, even for errors, refused/incomplete generation, missing usage,
  invalid answers, or responses discarded after the deadline. These counters measure
  reserved capacity, not actual usage. This conservative policy can leave capacity unused.
- The allowance covers potential **generated output, including reasoning tokens in the
  OpenAI version**. It excludes input tokens and all dollar accounting. It is not a
  billing cap. Cache hits avoid new backend calls but do not undo earlier reservations.
- At most two profiles are attempted for one query. A session allows at most ten
  attempts by configuration (two by default), at most 100000 reserved output tokens,
  and a deadline of at most 300 seconds. Zero calls or zero tokens block uncached work.
- Time forecasts gate admission; a forecast is not a latency promise. The backend gets
  the remaining time capped at 30 seconds. The deadline is cooperative: an arbitrary
  blocking callback cannot be forcibly stopped. Late successful results are discarded
  and not cached; checks stop subsequent attempts. SDK/network timeouts are not an
  exact wall-clock or billing guarantee.
- Successful, non-degraded answers enter an LRU cache keyed by the exact query and
  requested detail. The cache has eight entries by default (maximum 32, zero disables it).
  Degraded, invalid, failed, and late results are not cached. Expired sessions do not
  serve cache entries. The cache is per agent/session, with a fixed backend/configuration;
  it is not provider prompt caching, persistent storage, or shared user memory.
- The controller is synchronous and intended for one caller at a time. It does not
  provide concurrent or distributed budget enforcement. Do not mutate its backend,
  budget, or accounting during a session; create a new agent for changed configuration.
- Queries contain at most 1000 raw characters. Answers contain non-whitespace text
  and at most 3000 raw characters, including surrounding whitespace. These checks
  validate shape and size, not factual correctness or answer quality. More resources
  and a detailed profile do not guarantee a better answer or that a model actually
  follows the requested level of detail; strict mode enforces profile selection.
- A known transient backend failure permits a lower-resource alternative only when
  both policy and remaining resources allow it. Other failures stop with `failed`;
  private exception details are not returned. No successful answer is fabricated.

## Optional OpenAI version

[Setup and usage](openai_version/README.md). Both profiles default to configurable
`gpt-6-astra`, with different effort/output caps; a separate economy model can be
configured. The same controller, cache, and reservations govern all model attempts.

Tests use fake model responses and a controlled clock. They verify admission,
reservations, fallback classification, cache boundaries/eviction, output bounds,
late-result handling, request options, and cleanup without live API calls.

Next: **Pattern 17 — Reasoning Techniques**.

Injected clocks must return finite, nondecreasing numeric readings. Invalid readings
raise an error before a further action/dispatch or late answer is released. Stateful
controllers reject subsequent work after a clock fault; create a new controller.
