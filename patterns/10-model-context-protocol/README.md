# Pattern 10: Model Context Protocol (MCP)

MCP standardizes how a host discovers and uses a server's tools, resources, and
prompts. This original exercise follows Chapter 10 of Antonio Gulli's *Agentic
Design Patterns*, using a real local server and the official MCP Python SDK v2.

**Host → connect/negotiate → discover → read context or call tool → receive protocol result**

The demo contains only fictional support tickets. There are no account changes,
file-management tools, outgoing messages, HTTP listeners, or external data calls.
The client starts the server as a separate process and communicates over stdio.

## How it differs from Pattern 05

Tool Use defines functions inside an application and lets a model request them.
MCP adds a standardized client/server boundary: a client discovers schemas and
capabilities from a separate server, then invokes them through the protocol.
The server is reusable across compatible hosts; it does not call a model itself.

The local example has no model at all. The optional OpenAI host bridges discovered
MCP tools into OpenAI function definitions and sends chosen calls back through
MCP. Function calling and MCP work together at different boundaries.

## Three server capabilities

| Capability | Name | Purpose |
| --- | --- | --- |
| Tool | `get_ticket(ticket_id)` | Read fictional ticket T-101, T-102, or T-103 |
| Tool | `list_tickets(priority)` | Filter fictional tickets by `high` or `normal` |
| Resource | `support://policy` | Load policy text as host-selected context |
| Prompt | `triage_request(request)` | Render a reusable triage message template |

Tools execute functions. Resources provide data. Prompts render templates;
getting one does not run a model. In this demo, the host explicitly selects the
policy resource and triage prompt. The SDK manages protocol negotiation,
capabilities, request/result framing, schema generation, and subprocess lifecycle.

## Free local setup

**Pattern 10 requires Python 3.11+** because it uses the current SDK v2 API.
Patterns 01–09 still support Python 3.10. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r patterns/10-model-context-protocol/requirements.txt
python patterns/10-model-context-protocol/app.py
python patterns/10-model-context-protocol/examples/basic_example.py
python patterns/10-model-context-protocol/examples/advanced_example.py
```

Installing packages requires internet access. Running the local examples afterward
uses no API key, model service, TCP connection, or paid API. The free MCP SDK is
required, unlike the earlier standard-library local demos. The binary-only install
avoids building native dependencies or installing a compiler on your machine.

You do not need to start the server separately. The client launches the repository's
`server.py` with the same Python interpreter and stops it when the connection
closes. SDK subprocess defaults pass a minimal environment rather than inheriting
all exported variables; this read-only server needs no OpenAI key.

## Basic output

```text
Connected to: Support Lab
Discovered tools: ['get_ticket', 'list_tickets']
MCP tool status: success
Tool result: {'ticket': {'ticket_id': 'T-101', 'priority': 'high',
'category': 'billing', 'status': 'open',
'summary': 'Customer reports a duplicate subscription charge.'},
'source': 'simulated demo data'}
```

The result comes through a real MCP request to the separate server process.
`app.py` also prints the negotiated protocol version, discovered resource/prompt
names, loaded context, and structured tool observation.

## Advanced output

```text
Resources: ['support://policy']
Prompts: ['triage_request']
Policy resource: [fictional support policy text]
Rendered prompt: [triage template with the supplied request]
High-priority tickets: [T-101 and T-102, labelled simulated data]
Missing ticket: error ... Demo ticket T-999 was not found
Invalid arguments: error
No model request or real ticket update occurred.
```

These lines are shortened for readability. A missing record or invalid input is
an MCP tool result with `is_error=True`, not a successful empty record. The host
checks that flag before reading structured data. SDK diagnostics for deliberate
error cases may also appear on stderr; stdout carries protocol messages only in
the server process and human-readable demo output in the host process.

## Files, boundaries, and results

- `server.py`: standalone official-SDK server, typed tool results, resource, prompt.
- `app.py`: fixed local connection, bounded discovery pagination, context loading,
  allowlisted tool dispatch, and structured success/error observations.
- `examples/`: one-tool discovery plus resources, prompts, filtering, and errors.
- `openai_version/`: optional model host using the same MCP server.

The host permits only `get_ticket` and `list_tickets`. Tool annotations describe
read-only/idempotent behavior but are hints, not security controls. Actual server
handlers read only their fictional in-memory catalog and return copied data.
There is no arbitrary URL, executable, shell command, or filesystem path supplied
by a model. Discovery follows pagination with cursor-loop detection and a ten-page
limit. MCP request reads have a ten-second timeout; connection contexts clean up
on success and caller failure.

A `ToolObservation` records name, arguments, `success`/`error`, output, and error
text. Successful tool responses must include structured objects; tool failures
retain their error without fabricated data. Transport/protocol failures propagate.
MCP standardizes transport and discovery, not the truth or usefulness of data.

This is a local, single-domain demo, not a remotely deployed or authenticated
service. Real remote deployments need their own access and trust design. It does
not configure any MCP connection in Codex or another desktop app.

## Offline tests and references

```bash
python -m pytest patterns/10-model-context-protocol/tests -q
```

Tests use the real SDK with in-memory protocol transports plus actual stdio
subprocess checks. OpenAI responses are faked; network connections are blocked
in the test process. The server itself contains no network operations. Tests
cover discovery, schemas, resources/prompts, filters, errors, client cleanup,
model replay, and budgets. No OpenAI SDK/key is required for the suite.

GitHub Actions runs full MCP checks on Python 3.11, 3.12, and 3.14. Its Python 3.10
job retains earlier-pattern coverage and explicitly skips the two MCP test modules
and MCP demos because v2 requires 3.11+.

References: [official SDK first steps](https://py.sdk.modelcontextprotocol.io/get-started/first-steps/),
[client and result types](https://py.sdk.modelcontextprotocol.io/client/),
[stdio and in-memory transports](https://py.sdk.modelcontextprotocol.io/client/transports/).
The book uses older FastMCP/ADK examples; this implementation uses the current
`MCPServer`/`Client` SDK v2 interfaces instead.
