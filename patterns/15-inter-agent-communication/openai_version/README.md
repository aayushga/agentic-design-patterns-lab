# Optional OpenAI specialist for A2A

The coordinator, Agent Card, messages, task state, and artifacts use the same free
local A2A implementation. An `AsyncOpenAI` responder generates the triage report
instead of the deterministic rule. This does not send tickets to another hosted
agent or open a server port.

Use fictional tickets. Only the ticket is sent to OpenAI, without task history.
The host validates the JSON report and publishes it as a task artifact. Invalid
JSON, refusal/empty output, incomplete/failed responses, timeouts, or SDK exceptions
produce a failed task with no artifact. The report is advice, not an account action;
field validation does not guarantee the model's recommendations are correct.

## Setup

From the repository root, with Python 3.10+:

```bash
python -m pip install --only-binary=:all: -r patterns/15-inter-agent-communication/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
python patterns/15-inter-agent-communication/openai_version/openai_a2a.py --category billing --issue "An invoice appears twice."
```

`.env.example` documents the settings; the script does not automatically load `.env`.
Missing `OPENAI_API_KEY` produces a clear error before creating the SDK client.
The default model is `gpt-6-astra`, using Responses, low reasoning effort, and strict
structured outputs. `openai_session(model=...)` overrides `OPENAI_MODEL`, which
overrides the default. Any override must support these API features.

**Cost:** the CLI submits one ticket, with at most one billable model attempt.
Missing issue details and rejected tickets make zero model requests. SDK retries
are disabled, request timeout is 30 seconds, output is capped at 1500 tokens, and the host
deadline is 35 seconds.
The reusable session makes at most one model request per valid complete ticket;
its per-task submission limit is three. Creating more tasks can incur more calls.
The SDK client closes on session exit; requests use `store=False`. There is no live
model quality, latency, or account-access assertion in the offline test suite.

A successful run has the same task ID, context ID, completed state, and JSON artifact
shape as the local example, with model-written summary and next_step text.
The local examples and all tests can be run without an API key or API charges.

[Responses structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
