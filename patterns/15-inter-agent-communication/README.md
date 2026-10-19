# Pattern 15: Inter-Agent Communication (A2A)

A coordinator discovers a specialist's **Agent Card**, delegates a fictional
support ticket through the official **A2A Python SDK**, and receives a tracked
**Task** with a structured **Artifact**. The specialist can request missing input;
the coordinator resumes the same task using its task and context IDs.

This is an original, simplified exercise inspired by Chapter 15 of Antonio
Gulli's *Agentic Design Patterns*. It uses SDK 1.x / protocol 1.0, whose protobuf
models, supported interfaces, and `SendMessage` / `GetTask` methods replace the
older API shown in the book. It does not reproduce the book's code.

## What this teaches

- **Discovery:** fetch `/.well-known/agent-card.json` and inspect the advertised skill.
- **Delegation:** send a user Message with a unique message ID via JSON-RPC.
- **Lifecycle:** submitted → working → completed, or input_required → follow-up;
  invalid tickets are rejected and responder errors produce failed tasks.
- **Correlation:** preserve task and context IDs when resubmitting a complete ticket.
- **Results:** retrieve the task and its JSON triage-report artifact with `GetTask`.

Pattern 07 coordinates local specialist functions. Pattern 10 uses MCP to discover
and call tools, resources, and prompts. A2A delegates work to an agent through a
protocol boundary without exposing its internal implementation. Here the
specialist is deliberately a small rule-based responder so the communication is
easy to inspect; the optional model can replace its report-generation function.

```text
Coordinator → discover Agent Card → support specialist
Coordinator → SendMessage(ticket) → task: input_required
Coordinator → SendMessage(full ticket, same task/context IDs)
            ← task: completed + triage-report artifact
Coordinator → GetTask(task ID) → stored task and artifact
```

## Run locally for free

Python 3.10+; from the repository root:

```bash
python -m pip install --only-binary=:all: -r patterns/15-inter-agent-communication/requirements.txt
python patterns/15-inter-agent-communication/app.py
python patterns/15-inter-agent-communication/examples/basic_example.py
python patterns/15-inter-agent-communication/examples/advanced_example.py
python -m pytest patterns/15-inter-agent-communication/tests -q
```

You can also run `python -m pytest` from this pattern folder. No OpenAI package,
API key, account access, or billable request is needed for these commands. Installing
packages requires internet access; running these examples does not.

The real SDK client and server exchange serialized HTTP/JSON-RPC using httpx's
in-memory ASGI transport. **No network port is opened** and `support.local` is a
fixed local placeholder, not a remote service. This teaches the protocol without
server setup. It is not a demo of two independently deployed services.

Basic example: discover the agent, submit a complete billing ticket, inspect its
artifact, then retrieve the stored task. Representative output (IDs vary):

```text
Agent: DemoDesk support specialist
Skills: triage_support
{
  "task_id": "<generated task ID>",
  "context_id": "<generated context ID>",
  "state": "completed",
  "message": "Triage report prepared. The underlying issue is not marked resolved.",
  "artifacts": [{
    "name": "triage-report",
    "data": [{
      "priority": "normal",
      "summary": "An invoice appears twice.",
      "next_step": "Ask billing to review the invoice; no refund has been approved."
    }]
  }]
}
Retrieved task: <same task ID> completed
```

The advanced example shows four outcomes: missing details (`input_required`),
resuming the same task (`completed` with an artifact), an unsupported skill
(`rejected`), and a simulated specialist exception (`failed`, no artifact).
The follow-up contains the **entire ticket**, not a partial patch. Completed means
report generation completed; no refund, message, or account change is performed.

## Scope and bounds

- One coordinator and one specialist advertise `triage_support`; allowed categories
  are billing, support, and sales. Ticket text is at most 3000 characters, with an
  issue of at most 2000 characters. The local summary uses its first 1000 characters.
  Extra fields and unknown skills are rejected.
- At most three ticket submissions per task in this session. The fourth is rejected.
  A responder gets one attempt and a cooperative 35-second deadline. SDK persistence
  tracks task state; a separate per-task counter avoids asynchronous history races.
- Each complete valid ticket produces at most one artifact after report validation.
  Failed generation never becomes a successful fallback report.
- Task store and counters are in memory for the session and disappear when it ends.
  This is not durable storage, an idempotency service, or an unbounded server.
- Streaming and push notifications are disabled. Cancellation is explicitly unsupported.
  Unknown task IDs and sends to completed tasks produce SDK protocol errors.
- HTTP clients and the request handler are closed on exit. SDK 1.2.2 may log a
  dispatcher shutdown warning during its forced queue cleanup; tests verify the
  final report is stored and the clients close. The demo does not suppress SDK logs.
- Agent Cards advertise capabilities; they do not establish trust. Authentication,
  authorization, TLS, remote discovery, and persistent queues belong in a deployment
  exercise. Do not expose this unauthenticated local app as a public service.

## Optional OpenAI specialist

[Setup and usage](openai_version/README.md). The same A2A lifecycle stays under host
control; only the specialist's report generation uses a model. Tests cover it with
fake async responses and real local A2A exchanges, never live API calls.

## References

- [Official A2A Python SDK](https://github.com/a2aproject/a2a-python)
- [SDK 1.0 migration guide](https://github.com/a2aproject/a2a-python/blob/main/docs/migrations/v1_0/README.md)
- [A2A specification](https://a2a-protocol.org/latest/specification/)

Next: **Pattern 16 — Resource-Aware Optimization**.
