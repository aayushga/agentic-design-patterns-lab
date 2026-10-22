# Optional OpenAI Exception Handling and Recovery

After a validated fictional ticket lookup, the official OpenAI Python SDK selects
a practical next step through the Responses API and strict structured output.
The application owns recovery: it classifies expected SDK failures, retries only
transient cases, and can fall back to a local next-step rule. Python renders the
final message, preserving lookup provenance and avoiding model-written account facts.

Default model: `gpt-6-astra`, low reasoning effort. Explicit Python `model=` takes
precedence over `OPENAI_MODEL`, then the default. Overrides must support Responses,
structured outputs, and low reasoning effort.

## Setup

Python 3.10+; in your virtual environment, from the repository root:

```bash
python -m pip install -r patterns/12-exception-handling-and-recovery/openai_version/requirements.txt
cp patterns/12-exception-handling-and-recovery/openai_version/.env.example patterns/12-exception-handling-and-recovery/openai_version/.env
# Edit the .env file with your own key, then export it:
set -a
source patterns/12-exception-handling-and-recovery/openai_version/.env
set +a
python patterns/12-exception-handling-and-recovery/openai_version/openai_recovery.py
```

The script reads exported variables and does not load `.env` automatically.
Missing `OPENAI_API_KEY` is a clear configuration error before lookup or client
creation. Never commit secrets. The local examples and offline tests remain free.

**Running this optional version can incur API charges.** It defaults to at most
two model attempts, including the first request; failed attempts also count.
The SDK uses `max_retries=0` so its built-in retries cannot multiply the controller's
budget. Each request has a 30-second timeout. This is not a total run deadline.

```bash
python patterns/12-exception-handling-and-recovery/openai_version/openai_recovery.py --max-model-attempts 1
python patterns/12-exception-handling-and-recovery/openai_version/openai_recovery.py --scenario outage
```

`--scenario` injects a lookup failure, not a model/API failure. Lookup permits
three primary fixture reads and at most one cache read; these are local and free.
An unavailable lookup skips the model entirely. The model limit is independently
configurable from 1 to 5. Both the lookup and model use the same recovery controller.

## What recovers and what stops

| Model outcome | Application behavior |
| --- | --- |
| Connection failure, timeout, HTTP 408/409/5xx | Retry within the attempt budget |
| Response object with `status="failed"` and `server_error` or `rate_limit_exceeded` | Retry within the same model attempt budget, even though no HTTP exception was raised |
| HTTP 429 with `rate_limit_exceeded` or `slow_down` | Retry according to bounded wait policy |
| Quota/billing or unrecognized HTTP 429 | Stop without retries or model fallback |
| HTTP 400/401/403/404/422 or other terminal status | Stop and report a safe classification |
| Exhausted transient failures | Use one validated local rule, labelled degraded |
| Malformed/incomplete/empty/refused response or invalid selection | Reject the output and use the local rule without another model request |
| Unexpected SDK/application bug | Propagate; the client still closes |

Other failed response objects, including missing or unrecognized error codes, use
the existing non-completed-output fallback path without automatic retries. Failure
messages from response objects are not copied into the result.

The adapter reads `retry-after-ms`, numeric `Retry-After`, and HTTP-date
`Retry-After`. Valid server delays are respected; a delay beyond the policy's
two-second cap defers primary retries and permits the local fallback immediately.
No early repeat request is sent to the server. Invalid hints use exponential
backoff and jitter. Raw SDK error messages are not included in the result.

## Output and interpretation

A valid model selection looks like:

```json
{"ticket_id": "T-101", "next_step": "request_invoice_details"}
```

Only the matching ticket and a category-appropriate next step are accepted.
The output contains separate `lookup` and `model_selection` results with their
own events and status. A successful model selection cannot turn cached data into
a current primary result. If model recovery exhausts its budget, the message says:

```text
Model selection unavailable; a local rule supplied the next step.
```

Terminal model failures leave the selection unavailable and request human review;
the deterministic ticket-status message can still be shown. No human is contacted.
The CLI exits with code 1 when lookup or model selection is unavailable, while
valid degraded fallback results exit normally. Missing SDK or unexpected failures
produce a generic CLI error rather than printing raw service diagnostics.

The client closes on success and failure. Requests use `store=False`; that option
does not establish an account's retention policy. Retrying a generation can incur
additional charges; no live model quality, latency, or account access was measured.
All ticket data is fictional and no account changes or outgoing messages occur.

References: [official Python SDK error handling and retries](https://developers.openai.com/api/reference/python),
[rate-limit recovery](https://developers.openai.com/api/docs/guides/rate-limits).

Request safeguards: output is capped at 1000 tokens per attempt, response
storage is disabled (`store=False`), SDK retries are disabled, and clients close on
success or failure. SDK timeouts and cooperative application deadlines are not a
hard whole-run deadline. Token/request caps do not cap input charges or dollar spend.
