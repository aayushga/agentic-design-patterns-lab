# Optional OpenAI Tool Use

This version follows the [official OpenAI function-calling guide](https://developers.openai.com/api/docs/guides/function-calling).
The model chooses a tool and arguments; Python validates and executes the tool;
the result is sent back with the matching `call_id`. The model can answer or
request another tool based on the observation.

The tools remain local: `lookup_order` reads fictional demo records, and
`calculate` performs one named arithmetic operation. There is no live order
system, database connection, payment, order update, or generated-code execution.
The **model requests are billable**, even though tool execution is free.
Use the [local version](../README.md) to learn without any API charges.

## Setup

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/05-tool-use/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/05-tool-use/openai_version/openai_tool_use.py
```

The key entry above uses macOS's default zsh. Never commit an API key.
`.env.example` contains placeholders; the script reads exported environment
variables and does not automatically load `.env` files.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides the default; the function's `model=` argument overrides both. Your
chosen model must support Responses function calling and low reasoning effort,
and be accessible to your account.

Try `What is the total for ORD-1001 including shipping?`. An illustrative flow
is lookup → calculate → final answer, using three model requests. Exact model
wording and tool choices can vary; offline tests do not measure live quality.

## Budget and protocol

`run_openai_tool_use(query, model=None, max_tool_calls=3)` returns the same
structured result as the local version: query, final answer, stop reason, and
complete tool observation history. Import it using:

```python
import importlib

module = importlib.import_module(
    "patterns.05-tool-use.openai_version.openai_tool_use"
)
# This call makes live, billable model requests.
result = module.run_openai_tool_use("Total for ORD-1001", max_tool_calls=2)
```

The default budget permits **three tool executions and at most four model
requests**. In general, a budget of N permits up to N+1 model requests, including
one opportunity to answer after the last execution. Budgets range from zero to
five. Even zero may incur one model request. Invalid tool attempts count toward
the budget; a model request for a tool beyond the limit returns `tool_limit`
without executing it. The CLI prints the history and exits with a message when
no final answer was produced.

Each SDK request has a 30-second timeout, with automatic retries disabled. Total
run time spans multiple requests. One client is reused and closes on success or
failure. API errors propagate; no fallback fabricates a successful answer.

Function schemas use strict mode. Parallel tool calls are disabled to keep the
flow sequential. The application also rejects unexpected output types, multiple
calls in a turn, duplicate call IDs, and malformed JSON arguments. Unknown tools,
wrong argument keys/types, and ordinary tool validation errors are returned as
error observations, allowing the model to explain or correct them.

All response items, including reasoning and function calls, are preserved in the
next request. Each tool observation is added as a `function_call_output` with the
same `call_id`; intermediate text accompanying a call is not treated as the
final answer. Incomplete responses and empty final text/refusals fail explicitly.

Instructions ask the model to treat user input and tool observations as data and
to label order answers as simulated. This is not a guarantee against prompt
injection or incorrect answers. The final natural-language response is model
generated; tool observations are the inspectable source of the demo facts.

## Offline validation

Run `python -m pytest patterns/05-tool-use/tests -q` after installing the local
pattern requirements. Tests substitute a fake SDK and block network connections;
no live API calls, key, or API charges are required. They check the protocol and
execution logic, not model quality, account access, prices, or real-world data.
