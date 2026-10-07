# Pattern 05: Tool Use (Function Calling)

Tool Use lets an agent choose a function, supply its arguments, receive the
result, and use that observation to answer or choose another tool.

**Query → choose tool and arguments → validate → execute → observe → answer or repeat**

This follows Chapter 5 of Antonio Gulli's *Agentic Design Patterns*. It is an
original, simplified implementation using two ordinary Python functions:

| Tool | Inputs | Result |
| --- | --- | --- |
| `lookup_order` | `order_id`, such as `ORD-1001` | Fictional status, item amount, shipping fee, currency |
| `calculate` | `operation`, `left`, `right` | Addition, subtraction, multiplication, or division result |

All order records are clearly labelled **simulated demo data**. The tools make
no network calls, change no orders, and do not execute generated code.

## Difference from Routing

Routing chooses a handler for an intent and returns its response. Tool Use
chooses a function **and arguments**, then returns the function's result to the
decision-maker. It can choose another tool using the returned values. For example,
it first looks up an order, then calculates its total from the returned amounts.

Prompt Chaining follows a fixed sequence, Parallelization runs independent work
concurrently, and Reflection revises a draft using critique. This pattern focuses
on the boundary between a decision-maker and executable functions.

## Free local version

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/05-tool-use/app.py
python patterns/05-tool-use/examples/basic_example.py
python patterns/05-tool-use/examples/advanced_example.py
```

The local decision-maker uses a deliberately small command grammar, not an LLM:

- `status of ORD-1001`: look up the order and answer from its observation.
- `total for ORD-1001`: look up the order, then add its item amount and shipping fee.
- `calculate 12 + 8`: perform arithmetic; `-`, `*`, and `/` also work.
- Other queries return help without executing a tool.

The two fictional records are `ORD-1001` and `ORD-1002`. Order IDs are matched
case-insensitively in local queries. This is a learning exercise, not a live
customer-support application or general natural-language parser.

## Basic example output

```text
Query: What is the status of ORD-1001?
Tool call: lookup_order({'order_id': 'ORD-1001'})
Tool result: {'order_id': 'ORD-1001', 'status': 'shipped', 'items_total': 120.0, 'shipping_fee': 10.0, 'currency': 'USD', 'source': 'simulated demo data'}
Final answer: Demo order ORD-1001 is shipped (simulated data).
Stop: completed
```

## Advanced example output

The advanced example demonstrates three separate situations:

1. **Dependent calls:** lookup returns `items_total=120.0` and `shipping_fee=10.0`;
   the next call is `calculate(operation='add', left=120.0, right=10.0)`.
   Final answer: `Demo order ORD-1001 total including shipping: 130.00 USD (simulated data).`
2. **Tool error:** `ORD-9999` is missing. The observation has `status='error'`,
   and the final answer explicitly says the demo order was not found.
3. **Call limit:** the total query has a budget of one call. Lookup succeeds,
   but calculation cannot run. The result has `stop_reason='tool_limit'` and
   `final_response=None`, preserving the completed lookup for inspection.

## Python API and result

Use `importlib.import_module("patterns.05-tool-use.app")` from the repository
root to import the module with its hyphenated directory name, then call
`run_tool_use(query, max_tool_calls=3)`.

| Field | Meaning |
| --- | --- |
| `original_query` | User's input |
| `final_response` | Answer, or `None` if the call limit prevented completion |
| `stop_reason` | `completed` or `tool_limit` |
| `tool_history` | Call ID, tool name, arguments, success/error status, output/error |

The call budget accepts integers zero through five and defaults to three.
Failed attempts count toward it. A final answer is still allowed after the last
permitted tool; another requested tool stops the loop. A completed result means
an answer was produced, not that every tool succeeded or that the answer was
independently verified. Inspect the observations when reviewing results.

A custom `decider(query, history)` can replace the local decision rules. It must
return a `Decision` with exactly one `ToolCall` or non-empty `final_response`.
The engine sends each execution's observation back to it, enabling correction
of invalid arguments within the budget. Duplicate call IDs fail explicitly.

## Execution boundary

Only the explicit `TOOLS` registry can dispatch functions. Tool argument keys
must match the expected keys exactly; functions validate value types. The
calculator accepts finite numeric operands between -1e12 and 1e12, rejects
booleans and division by zero, and never uses `eval` or a shell. Tool validation
errors become observations. Malformed decisions and unexpected exceptions
propagate rather than being reported as success.

Real integrations would need authentication, access controls, and appropriate
approval for actions. Those are outside this read-only demo's scope.

## Optional OpenAI version and offline tests

[OpenAI setup](openai_version/README.md) uses the official SDK and Responses
function calling. OpenAI chooses the next function and arguments; the same local
execution boundary runs it and sends back a correlated tool result. The default
model is `gpt-6-astra`, with a configurable override.

```bash
python -m pip install -r patterns/05-tool-use/requirements.txt
python -m pytest patterns/05-tool-use/tests -q
```

Tests use fake SDK responses and block network connections. They cover dependent
calls, result replay, error recovery, argument validation, duplicate IDs, budgets,
malformed model responses, missing keys, and client cleanup. No API key or real
OpenAI SDK is needed to run them.
