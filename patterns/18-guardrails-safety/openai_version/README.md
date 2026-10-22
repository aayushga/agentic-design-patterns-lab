# Optional OpenAI action proposer with host guardrails

The official OpenAI Python SDK and Responses API choose one structured proposal:
`lookup_order`, `request_refund`, or `unknown`, bound to a requested order ID.
Host code enforces identity, authorization, action permissions, and outgoing facts.
No model-generated freeform reply, customer ID, or order fact is accepted.

## Setup

Python 3.10+; from the repository root:

```bash
python -m pip install --only-binary=:all: -r patterns/18-guardrails-safety/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
python patterns/18-guardrails-safety/openai_version/openai_guardrails.py --query "Where is my order?" --order-id ORD-101
```

Scripts do not automatically load `.env`; `.env.example` documents the exported
settings. Explicit `model=` overrides `OPENAI_MODEL`, which overrides `gpt-6-astra`.
Overrides must support Responses, low reasoning effort, and structured outputs.

Input/identity/ownership failures stop before SDK import and do not need an API key.
For an otherwise eligible request, a missing key produces a structured
`unavailable` result with `Missing OPENAI_API_KEY` and no tool execution. This is
a clear configuration error; it is not a billable model request.

## Data and authority

The model receives only the bounded, redacted query and requested order ID, in
user input. Trusted instructions are separate. It receives no caller customer ID,
order record, or unrelated customer data. The demonstration redaction patterns are
limited; use fictional requests and do not send real sensitive information.

A valid proposal does not grant permission. The host requires the same requested
order ID and an allowed action. Refunds return `human_review` without a write or
submitted request. An order lookup runs locally and must pass the public-field and
snapshot checks before a host-built reply is returned.

Extra proposal fields, changed order IDs, unsupported actions, malformed or oversized
JSON, and output violations stop the flow. Request failures, refused/empty output,
and non-completed responses never trigger a second request or an unguarded local
fallback. The audit records fixed stage/decision codes, not raw model/error text.

## Cost and verification

**At most one billable model attempt per eligible run.** Input screening, redaction,
ownership checks, and local order reads are free. The model call uses a 1000-token
output cap, low reasoning effort, a 30-second SDK timeout, `store=False`, and disabled
SDK retries. The client closes on exit. The cap includes generated reasoning/output,
excludes input charges, and is not a dollar limit; incomplete or timed-out generation
can still incur usage. Raw response text is limited to 1000 characters before JSON
parsing; host schema validation still runs after parsing.

The full result uses the same fields as the local example. `proposal_attempts`
counts callback invocation, including the missing-key branch; it is not an API
billing counter. A `completed` result means an authorized fictional snapshot was
returned, not that a real order or account was changed.

The [official safety guidance](https://developers.openai.com/api/docs/guides/agent-builder-safety)
discusses structured boundaries and layered controls. [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
constrain shape, while application code decides authorization. This example uses
the plain OpenAI SDK with explicit Python guards, not Agent Builder or Agents SDK
guardrail nodes. The [local guide](../README.md) lists trust assumptions and limits.

Tests use fake responses and require neither the OpenAI SDK nor a real key. They
check the host gates, sanitized request construction, response handling, and cleanup,
not live model quality, attack resistance, account access, or actual costs.
