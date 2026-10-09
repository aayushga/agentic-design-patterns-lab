# Optional OpenAI Multi-Agent Collaboration

This version uses the official OpenAI Python SDK and Responses API. Each role
has a separate prompt and request: a supervisor chooses specialists, selected
specialists produce findings, and a writer receives their handoffs. Assignment
and finding responses use [structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

Python manages delegation and delivery. All roles share the selected model and
one SDK client, but receive separate role-specific contexts. This is a lightweight
role workflow, not the OpenAI Agents SDK, autonomous workers, or independent
factual verification. Use the [local example](../README.md) for a free simulation.

## Setup and run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/07-multi-agent-collaboration/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/07-multi-agent-collaboration/openai_version/openai_collaboration.py
```

The key entry above uses macOS's default zsh. Never commit a real API key.
`.env.example` contains placeholders only. Scripts read exported environment
variables and do not automatically load `.env` files.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides it; the Python function's `model=` argument overrides both. Your model
must support Responses, structured outputs, and low reasoning effort, and be
accessible to your account.

Try: `I was charged twice. The app crashes during upload.` The supervisor can
assign both roles, and the writer combines their findings into a draft. Exact
wording and assignments may vary. No account lookup, refund, repair, or outgoing
message is performed; these are analysis and writing requests only.

## Request counts and failures

| Flow | Model requests |
| --- | --- |
| Supervisor requests clarification | 1 |
| One specialist plus writer | 3 |
| Two specialists plus writer | 4 |

A failed specialist still consumes its attempted request. If all selected
specialists fail, the writer is skipped; no final reply is produced. With partial
success, the writer receives both valid findings and explicit error handoffs.
The coordinator marks the result `needs_review` and prefixes a human-review
notice even if the writer omits one. Writer failure returns `failed`, retaining
the specialist trace. Supervisor failure or an invalid assignment stops before
delegation and propagates as an error.

Each assigned role runs once, with no recursive delegation or automatic retries.
Each SDK request has a 30-second timeout. Total time spans the sequential requests.
One client is reused and closes on success or failure. Failure details in handoffs
are sanitized; arbitrary SDK exception text is not printed as customer content.

## Communication and validation

The supervisor receives the ticket and role-selection instructions. Each
specialist receives the original ticket and only its own role instructions.
The writer receives the ticket plus structured handoffs identifying the sender,
recipient, success/error status, findings, and error. This delivery is explicit;
there is no hidden shared agent memory.

Strict JSON schemas describe assignments and findings. Local validation also
checks allowed unique roles, non-empty fields, one to three findings per
successful specialist, and evidence that appears exactly in the original ticket.
Malformed reports and invented excerpts are treated as specialist failures.

Exact ticket excerpts establish only what the customer reported. They do not
prove an assessment is correct. The final reply is model-generated; even multiple
roles can invent facts or share errors. Prompts ask for cautious assessments and
for input/handoffs to be treated as data, which is not a guarantee against prompt
injection. Review the final reply and handoff trace before using them externally.

The returned result has the same fields as the local version. The CLI prints it
and exits with a message when the workflow needs clarification/review or fails.
`completed` means usable outputs were produced, not that the ticket was resolved.

## Python call and offline tests

```python
import importlib
from dataclasses import asdict

module = importlib.import_module(
    "patterns.07-multi-agent-collaboration.openai_version.openai_collaboration"
)
# This makes live, billable model requests.
result = module.run_openai_collaboration(
    "I was charged twice. The app crashes during upload."
)
print(asdict(result))
```

Install the local pattern requirements and run
`python -m pytest patterns/07-multi-agent-collaboration/tests -q` for offline tests.
Tests use fake SDK responses and block network access. They need no real SDK or
key and incur no API charges. They validate communication and orchestration,
not live model quality, account access, or latency.
