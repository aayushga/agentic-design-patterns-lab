# Pattern 18: Guardrails/Safety Patterns

A fictional order-status assistant checks its input, caller context, proposed
action, tool access, and outgoing data. The local rule or optional model can
**propose** an action; host code decides whether it can execute and what can be
released. No model-generated prose is shown as an order fact or action result.

This original exercise is inspired by Chapter 18 of Antonio Gulli's *Agentic Design
Patterns*. It illustrates selected layers in a small support workflow, with no
external moderation service or production authentication system.

## Layers

| Layer | Host-enforced check | Failure behavior |
| --- | --- | --- |
| Identity | A trusted host Session is present | Stop before proposer/tool |
| Input | Raw/normalized/redacted query bounds, format, demo redaction and override patterns | Stop before proposer/tool |
| Authorization | Requested order belongs to the caller in the trusted fixture catalog | Same denial for missing and inaccessible orders |
| Proposal | Exact action/order schema; order ID matches the requested ID | Reject extra fields, arbitrary actions, and retargeting |
| Action | Only lookup_order can execute | Refund routes to human review; unknown proposals stop |
| Tool output | Exact public fields and values match the authorized snapshot | Discard the entire payload on mismatch or validation error |

```text
Query + requested order + trusted host identity
  → input screening/redaction → order ownership check
  → rule/model proposes an action → schema and target binding
  → read-only action gate → local lookup → output checks → host-built reply
```

The keyword rule or model may misclassify intent. Permission checks do not depend
on the input heuristic or on a model saying the request is safe. A missed override pattern still cannot change the host Session,
select another order, add a tool, or publish arbitrary model text through this flow.

Pattern 02 focuses on routing, Pattern 05 on tool interaction, and Pattern 13 on a
review/approval lifecycle. This example combines several boundaries; its
`human_review` outcome is only a direction to contact billing, not a queued review,
an approval workflow, or a submitted refund request.

## Run locally for free

Python 3.10+; from the repository root:

```bash
python -m pip install -r patterns/18-guardrails-safety/requirements.txt
python patterns/18-guardrails-safety/app.py
python patterns/18-guardrails-safety/examples/basic_example.py
python patterns/18-guardrails-safety/examples/advanced_example.py
python -m pytest patterns/18-guardrails-safety/tests -q
```

Local code uses only the standard library; pytest is needed for tests. No OpenAI
SDK, key, network service, or API charge is needed. You can also run `python -m
pytest` from this pattern folder.

The fixed demo Session is customer `C-100`, which owns `ORD-101` and `ORD-102`.
`ORD-202` belongs to another fictional customer. All statuses and dates are fixture
data, not live shipping information.

The basic example redacts an email, then reads an authorized order. Abridged output:

```json
{
  "status": "completed",
  "reply": "Demo order ORD-101 is shipped. Delivery estimate: 2026-11-03. No account changes were made.",
  "data": {
    "order_id": "ORD-101",
    "status": "shipped",
    "estimated_delivery": "2026-11-03"
  },
  "redacted_query": "Where is my order? My email is [REDACTED_EMAIL].",
  "redactions": 1,
  "proposal_attempts": 1,
  "tool_attempts": 1
}
```

The full result also contains a bounded audit of stage, decision, and fixed reason
code. It does not put raw requests, model responses, tool payloads, customer IDs,
or exception messages into audit events. `proposal_attempts` counts invocation of
the rule/model callback (including a missing-key check), not billable requests.
`tool_attempts` counts invocation of the local lookup callback.

The advanced example demonstrates:

```text
Instruction override: blocked; proposals=0; tools=0
Different customer's order: blocked; proposals=0; tools=0
Refund request: human_review; proposals=1; tools=0
Disallowed model action: blocked; proposals=1; tools=0
Unexpected private tool field: blocked; proposals=1; tools=1
Model changes the requested order: blocked; proposals=1; tools=0
```

The "model" proposals in that free advanced example are injected Python test
callbacks. They do not call an LLM. The output check discards contaminated payloads
instead of publishing their unapproved fields.

## Bounds and trust assumptions

- Queries must contain text and be at most 1000 raw characters. NFKC normalization
  and redaction are each followed by the same size check. Unsupported control
  characters and malformed order IDs are blocked; IDs use ASCII `ORD-` plus three digits.
- Regexes redact demonstrated ASCII email addresses, hyphenated SSN-shaped numbers,
  and `sk-`-shaped strings. The override screen checks a few bounded English phrases.
  These examples can miss sensitive data or attacks and can produce false positives.
  They are not complete PII detection, moderation, or a prompt-injection classifier.
- The result includes the redacted query for learning. It may still contain unmatched
  personal data. Do not treat it as safe for unrestricted production logging/sharing.
- Session is a **trusted host-supplied context**, not proof of authentication. The demo
  constructor accepts customer IDs; a deployed service must derive identity from
  authenticated server state, never a request/model-supplied customer ID. This code
  does not expose a network service or implement tokens, multi-tenant storage, or TLS.
- The immutable fixture catalog is the authority for ownership and order facts. A
  read receives one authorized Order; output must contain exactly order_id, status,
  and estimated_delivery and match that snapshot. This is a fixed-data illustration,
  not a freshness guarantee for remote order systems.
- No write tool exists in the default flow. A refund proposal cannot issue a refund.
  Output replies use host templates and validated public fields; model-provided
  claims, freeform messages, private notes, and extra fields are rejected.
- There is at most one proposal and one local read attempt per run, with no retries.
  The audit has at most seven events. Callback/guard failures stop without releasing
  order data or echoing private exception text.
- Injected callbacks are trusted application extension points for tests and demos,
  not user-supplied code or a sandbox. A Python callback can do anything the host
  permits; the default callbacks only use deterministic local fixtures. Real tools
  need their own enforced permissions, credentials, and side-effect controls.

## Optional OpenAI version

[Setup and usage](openai_version/README.md). Astra proposes only an action and order
ID. Input and ownership checks run before SDK import or use. All tool permissions
and output checks remain in the same host-controlled flow.

Tests exercise redaction boundaries, missing context, cross-customer access,
model retargeting, write attempts, malformed responses, contaminated/fabricated
output, guard exceptions, and fake SDK requests/cleanup. They do not establish
universal security or live model robustness. Layered controls reduce risk; this
small exercise is not a complete security boundary for a deployed application.

Next: **Pattern 19 — Evaluation and Monitoring**.
