# Optional OpenAI Reflection

This version uses the official OpenAI Python SDK and Responses API for a
support-reply **writer → critic → revision → recheck** loop. The writer and
critic use separate prompts with the same rubric. They share a model; this is
not an independent factual verification service.

Use the [free local version](../README.md) to learn the flow without API charges.

## Setup and run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/04-reflection/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/04-reflection/openai_version/openai_reflection.py
```

The key entry above is for macOS's default zsh shell. Never commit a real API key.
`.env.example` contains placeholders only; the script reads exported environment
variables and does not automatically load an `.env` file.

The default is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL` overrides
the default; the Python function's `model=` argument takes precedence over both.
The selected model must support Responses, structured outputs, and low reasoning
effort, and be available to your account.

## Requests, output, and stopping

With the default `max_revisions=2`, the maximum is **six billable requests**:
one draft, three critiques, and two revisions. Initial approval uses two.
A supplied `initial_draft` skips the first writer request. For a revision budget
of N, the maximum is `2N + 2` requests, or `2N + 1` with a supplied draft.
Valid budgets are zero through five.

Requests are sequential because each depends on earlier feedback. Each has
a 30-second SDK timeout and automatic retries are disabled. Total run time can
span several requests. The loop stops early on approval or a repeated draft.

Results have the same fields and review history as the local version.
Critiques use a strict JSON schema containing `approved` and `issues`; the
application also validates their types and consistency. The final returned
draft has been reviewed even when the budget is exhausted. Unapproved results
retain their issues; the CLI prints them and exits with a message that human
review is still needed.

Missing keys, malformed critiques, incomplete responses, refusals without text,
and request errors fail explicitly instead of being counted as approval. The
SDK client closes on success or failure. Ticket, draft, and feedback are passed
as data with instructions to ignore embedded commands; this does not guarantee
resistance to prompt injection.

The critic assesses courtesy, issue coverage, next steps, length, and unsupported
claims. Approval is a rubric judgement, not proof that facts are correct.
Offline tests validate orchestration and request construction. They do not
measure live quality, billing, latency, or account/model access.

## Call from Python

Because the pattern folder has a hyphen, use an import module name:

```python
import importlib
from dataclasses import asdict

module = importlib.import_module(
    "patterns.04-reflection.openai_version.openai_reflection"
)
result = module.run_openai_reflection(
    "I was charged twice.", max_revisions=1
)
print(asdict(result))
```

This call makes live API requests. The repository's test suite uses fake SDK
responses and blocks network connections, so tests need no key and incur no API
charges.
