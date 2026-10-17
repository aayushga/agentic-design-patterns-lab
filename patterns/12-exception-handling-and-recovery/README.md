# Pattern 12: Exception Handling and Recovery

Operational failures need a deliberate response: detect the problem, classify
it, retry only when useful, and return a truthful fallback or clear failure.
This original exercise follows Chapter 12 of Antonio Gulli's *Agentic Design
Patterns*, using a fictional support-ticket lookup.

**Attempt → validate → classify failure → bounded retry or fallback → report outcome**

The default implementation is free and uses only the Python standard library.
The optional OpenAI implementation applies the same recovery controller to model
requests after the lookup. No real ticket system, account, message, or database
is accessed or changed.

## Recovery policy

| Failure | Response |
| --- | --- |
| Temporary lookup/service failure | Retry with bounded exponential backoff and jitter |
| Attempts exhausted | Try the cached snapshot once, if enabled |
| Malformed or mismatched output | Reject it; try one validated fallback without repeating the malformed response |
| Not found or access denied | Stop; do not retry or bypass the failure through cache |
| Missing/invalid fallback | Report unavailable; do not invent a record |
| Unexpected programming error or cancellation | Propagate it rather than disguising it as a service outage |

`RetryPolicy.max_attempts` includes the initial call: the default is three primary
attempts, not three retries. Delays start at 0.25 seconds, double on each retry,
and cap at two seconds before jitter selects 50–100% of that value. There is no
sleep after the final failed attempt. The fallback has its own single attempt
and goes through the same validator.

A valid server `Retry-After` delay takes precedence over backoff. If that delay
exceeds the configured wait cap, primary retries stop instead of retrying early;
an allowed local fallback may still provide a degraded result. Attempt and delay
budgets are bounded, but this is not a total wall-clock deadline. Real I/O needs
its own timeout; the optional SDK requests use a 30-second timeout.

## Free local run

Python 3.10+; from the repository root:

```bash
python patterns/12-exception-handling-and-recovery/app.py
python patterns/12-exception-handling-and-recovery/examples/basic_example.py
python patterns/12-exception-handling-and-recovery/examples/advanced_example.py
```

No dependency installation, API key, internet connection, or paid service is
needed for these demos. Retry waits are simulated so the examples run immediately;
the printed delays show the recovery policy. Library functions use real sleeps
by default, with injectable sleeping and randomness for demos and tests.

### Basic example: recover on retry

```text
Ticket: T-101
primary attempt 1: transient (service_unavailable)
primary attempt 1: retry_scheduled | delay 0.25s
primary attempt 2: success
Lookup result: recovered
Reply: Primary demo snapshot. T-101: open. ...
```

The first simulated read fails, but the second succeeds. No cache is used.

### Advanced example: fallback and controlled failure

```text
OUTAGE: USE AN OLDER CACHE
primary attempt 1: transient (service_unavailable)
primary attempt 1: retry_scheduled | delay 0.25s
primary attempt 2: transient (service_unavailable)
primary attempt 2: retry_scheduled | delay 0.5s
primary attempt 3: transient (service_unavailable)
fallback attempt 1: success
Lookup result: degraded
Reply: Older cached demo snapshot; current status is unverified. ...

MALFORMED RESULT: VALIDATE BEFORE USE
primary attempt 1: invalid (invalid_record)
fallback attempt 1: success
Lookup result: degraded

ACCESS DENIED: DO NOT RETRY OR USE CACHE
primary attempt 1: terminal (access_denied)
Lookup result: unavailable

NO FALLBACK: REPORT UNAVAILABILITY
[three failed primary attempts]
Lookup result: unavailable
```

Excerpts are shortened. The primary fixture says `open`; the older cache fixture
says `waiting_for_details`, deliberately showing why fallback provenance matters.
These are seeded demo snapshots, not actual fresh data or a clock-based cache.
The unavailable reply asks for human review but does not send a notification.

## Results and boundaries

`app.py` prints structured JSON. Each `RecoveryResult` contains a validated value
or `null`, primary-attempt count, and an event history with stage, attempt,
outcome, safe error code, and any scheduled delay.

- `success`: primary succeeded on its first attempt.
- `recovered`: primary succeeded after a retry.
- `degraded`: a separately validated fallback supplied the value.
- `unavailable`: no acceptable value was returned.

Fallback is reduced functionality, not proof that the primary service recovered.
Events intentionally contain safe classifications rather than raw exception text,
which may include request details. There is no persistent log or background retry.

This example only retries reads and optional model generation. It does not retry
payments, sends, or other external writes; those require an idempotency or
compensation design. There are no transactions to roll back here, and no partial
record is published before validation. Circuit breakers and distributed retry
coordination are outside this small exercise.

Pattern 11 measures progress toward a goal. Pattern 12 decides what to do when a
particular operation fails. The book demonstrates layered location-lookup agents;
this implementation expresses the recovery policy directly in readable Python.

## Optional OpenAI version and offline tests

See [OpenAI setup](openai_version/README.md). Astra selects a constrained next-step
identifier; Python renders the reply from validated facts and retains cache warnings.

```bash
python -m pip install -r patterns/12-exception-handling-and-recovery/requirements.txt
python -m pytest patterns/12-exception-handling-and-recovery/tests -q
```

Tests use fake operations, SDK responses/errors, waits, and randomness. They cover
error classification, budgets, Retry-After, cache provenance, invalid output,
terminal failures, unexpected-error propagation, and client cleanup. Network
connections are blocked; neither an OpenAI SDK installation nor a key is needed.
