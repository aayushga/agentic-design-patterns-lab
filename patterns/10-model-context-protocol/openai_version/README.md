# Optional OpenAI + Local MCP

This host connects to the same local support MCP server as the free examples.
It discovers allowed tools, adapts their input schemas into OpenAI function
schemas, loads the policy resource and triage prompt, and asks the model what to
do. A selected function is invoked **through MCP**, then its observation is sent
back to OpenAI with the corresponding `call_id`.

**OpenAI chooses → host checks → MCP client calls server → server result → OpenAI answers**

This is a local MCP/function-calling bridge, not OpenAI's hosted remote-MCP tool.
A cloud model service cannot directly launch or reach your Mac's stdio server.
The Python host performs that communication. The server contains fictional,
read-only tickets and never receives an OpenAI API key.

## Setup

Use Python 3.11 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r patterns/10-model-context-protocol/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/10-model-context-protocol/openai_version/openai_mcp.py
```

The key entry above uses macOS's default zsh. Never commit a real key. The script
reads exported variables without automatically loading `.env` files;
`.env.example` contains placeholders only.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides it; the function's `model=` argument takes precedence. The model must
support Responses function calling and low reasoning effort and be available
to your account. Try `What does T-101 report?` or `Summarize high-priority tickets.`

Use the [free local demo](../README.md) to inspect MCP without paid model calls.
No external server, app connection, or local editor is needed for these examples.

## Cost and stopping behavior

The default `max_tool_calls=2` permits **at most three billable model requests**:
one to choose a tool, another to answer or choose the next tool, and a final
opportunity to answer after the second execution. No-tool answers use one request.
In general, a budget of N permits at most N+1 model requests. Valid budgets are
zero through five; even zero may incur one model request.

MCP discovery, policy loading, prompt rendering, and local tool execution are
free. They are not model-directed tool calls and do not consume that tool budget.
Failed model-directed attempts do consume it. A tool requested beyond the limit
is not executed; the result is `tool_limit` with no final answer. CLI output keeps
the completed observation history and exits with an explanatory message.

Each SDK request has a 30-second timeout and no automatic retries. MCP reads use
a ten-second timeout. Calls are sequential and total run time spans several
requests. Async context managers close the OpenAI client and stop the MCP server
on success or failure. Missing keys and invalid user inputs fail before launching
the server.

## Protocol and validation

The bridge handles this demo's flat required-argument schemas. It exposes only
discovered tools on the host allowlist, marks function schemas strict, and checks
argument keys before dispatch. The MCP server validates types, enum values, and
ticket-ID patterns. Errors become explicit model observations; unknown or
unallowed functions are not executed. Malformed JSON, multiple calls per model
response, duplicate call IDs, incomplete responses, and empty final text fail.

The complete model output, including reasoning and function-call items, is
preserved for the next request. Each result is added as a `function_call_output`
with its matching `call_id`. Intermediate text accompanying a tool call is not
counted as the final answer. This follows the
[OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).

The result contains `original_query`, `discovered_tools`, `status`,
`final_response`, and `tool_history`. `completed` means a final answer was produced,
not that every tool succeeded or that the model's prose is independently verified.
The server's result is the inspectable source for the fictional ticket facts.

Host instructions treat the resource, prompt, ticket data, and query as data and
ask the model to avoid invented facts or actions. This is not a guarantee against
prompt injection or inaccurate answers. The server is deliberately local and
read-only; this example does not establish trust in arbitrary remote MCP servers.

## Python call and offline validation

```python
import asyncio
import importlib
from dataclasses import asdict

module = importlib.import_module(
    "patterns.10-model-context-protocol.openai_version.openai_mcp"
)
# Live, billable model requests; the local server is launched and stopped automatically.
result = asyncio.run(module.run_openai_mcp("What does T-101 report?"))
print(asdict(result))
```

Tests use the real MCP protocol with fake OpenAI responses, requiring no installed
OpenAI SDK or API key. They incur no API charges. They validate local protocol
execution and model/tool message exchange, not live model quality, latency, or
account access.
