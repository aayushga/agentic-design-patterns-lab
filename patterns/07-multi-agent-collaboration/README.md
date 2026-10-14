# Pattern 07: Multi-Agent Collaboration

A team of specialized agents works toward one result through explicit delegation
and communication. This original exercise follows Chapter 7 of Antonio Gulli's
*Agentic Design Patterns*, using a small support-team workflow:

**Supervisor → selected specialists → structured handoffs → reply writer**

| Role | Responsibility |
| --- | --- |
| Supervisor | Assign billing, technical, both, or ask for clarification |
| Billing specialist | Identify the reported billing concern and suggest details to request |
| Technical specialist | Identify the reported app concern and suggest details to request |
| Writer | Compose one reply from the specialist messages, including unavailable work |

The local version simulates these roles with ordinary Python functions. The
optional OpenAI version uses separate prompts and requests for each role. Roles
have distinct responsibilities and explicit inputs/outputs; they are not separate
OS processes, autonomous background workers, or independently verified experts.

## How it differs from earlier patterns

Routing selects a handler. This supervisor can delegate one ticket to **multiple
specialists**, then pass their findings to another role. Prompt Chaining passes
outputs through a sequence; this exercise makes role ownership and the handoff
protocol explicit and chooses which specialists participate. Parallelization
focuses on concurrent work; this collaboration runs sequentially to keep its
communication trace easy to inspect. Collaboration does not require concurrency.

Reflection uses critique to improve a draft; Planning lays out steps and can
replan. This example demonstrates the book's supervisor and expert-team models,
not debate, consensus, peer-to-peer messaging, or a general multi-agent framework.

## Free local run

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/07-multi-agent-collaboration/app.py
python patterns/07-multi-agent-collaboration/examples/basic_example.py
python patterns/07-multi-agent-collaboration/examples/advanced_example.py
```

No SDK, key, network, or API charges are needed. No account is accessed, no refund
or repair occurs, and no reply is sent anywhere. The program only prints a draft.

The local supervisor uses substring keywords. Billing words include `charged`,
`invoice`, and `refund`; technical words include `crash`, `error`, and `upload`.
The matching is intentionally simple and can miss context or misinterpret
negation. Each local specialist selects a matching sentence and adds a cautious
assessment and a suggested next step. These are deterministic simulations, not
LLM analysis or verified account facts.

## Basic example

```text
Query: I was charged twice for my subscription.
Supervisor assigned: billing
Handoff: billing -> writer; success
Evidence: I was charged twice for my subscription.
Assessment: Billing issue reported; transaction records have not been checked.
Next step: Please share the relevant invoice number so billing can investigate.
```

The writer produces a courteous reply containing that evidence, assessment, and
next step, ending with `No account changes or fixes have been performed.`
The status is `completed`.

## Advanced example

For `I was charged twice. The app crashes during upload.`, both specialists run.
The writer receives separate messages identifying their senders and combines
billing's invoice request with technical support's error-message/app-version
request into one reply.

The demo also simulates a technical-specialist outage:

```text
Supervisor assigned: ['billing', 'technical']
billing -> writer: success; findings delivered
technical -> writer: error; Specialist failed or returned invalid findings
Final reply:
Some specialist work is unavailable; this reply needs human review.
[Billing findings and next steps, plus the unavailable technical analysis]
Status: needs_review
```

Successful work remains available. If no specialist succeeds, the writer is
skipped and no final reply is produced. An unsupported query, such as `Hello,
I need help.`, requests more details without running specialists or the writer.

## Result and communication contract

Import using
`importlib.import_module("patterns.07-multi-agent-collaboration.app")`, then call
`run_collaboration(query)`. `dataclasses.asdict(result)` gives JSON-ready data:

| Field | Meaning |
| --- | --- |
| `original_query` | Customer's input |
| `assignment` | Selected roles and supervisor's reason |
| `status` | `completed`, `needs_review`, `needs_clarification`, or `failed` |
| `final_response` | Draft reply, or `None` when production fails |
| `handoffs` | Sender, recipient, status, findings, and sanitized error for each specialist |
| `writer_error` | Explicit writer failure, if any |

Each successful handoff contains one to three `Finding` records. Each has
`evidence` copied as an exact non-empty ticket excerpt, an `assessment`, and a
`next_step`. Ownership is supplied by the coordinator; a specialist cannot
rename itself through its output. The exact-excerpt check verifies provenance
of that excerpt, **not the truth of the assessment or whether a next step is useful**.

The supervisor may assign only the two registered roles, each once. Invalid
assignments fail before any specialist runs. Missing, failed, or malformed
specialist outputs become error handoffs. The writer receives copies of the
handoffs, preserving the inspection trace. Failed handoffs force a trusted
human-review notice in any resulting reply. Empty/failed writer output returns
`failed` with no final reply and retains specialist messages.

`completed` means assigned roles and the writer returned usable outputs. It does
not mean an issue was resolved, an account was checked, or facts were independently
verified. Multiple agents can share the same blind spots and add cost or latency.

## Customize and test

`run_collaboration` accepts `supervisor`, `specialists`, and `writer` callbacks.
The supervisor returns `Assignment`; each selected specialist returns findings;
the writer receives the original query and handoff list. The registry is restricted
to known roles. Each role runs at most once; there is no recursive delegation,
retry loop, or unbounded conversation.

[Optional OpenAI setup](openai_version/README.md) uses the official SDK and
`gpt-6-astra` by default. The whole optional flow makes at most four billable
requests. The free simulation makes none.

```bash
python -m pip install -r patterns/07-multi-agent-collaboration/requirements.txt
python -m pytest patterns/07-multi-agent-collaboration/tests -q
```

Offline tests verify role selection, actual handoff delivery, evidence provenance,
partial failures, writer failure, protocol validation, and SDK request construction.
They replace SDK responses with fakes and block network connections, requiring
no real SDK or API key.
