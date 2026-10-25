# Optional OpenAI versions

[Back to the lab](../README.md) · [Free local setup](running-local.md)

All 21 patterns keep their model-backed implementation in an `openai_version/`
folder. Installation and the repository's mocked tests make no model requests.
Running an optional example deliberately makes billable requests.

## Common setup

Use a separate virtual environment. From the repository root, this installs the
Prompt Chaining adapter as an example; substitute your chosen pattern's path:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install --only-binary=:all: -r patterns/01-prompt-chaining/openai_version/requirements.txt
```

In Windows Command Prompt, activate with `.venv\Scripts\activate`. The examples use the tested
OpenAI SDK 2.x range; see the [dependency policy](dependencies.md). Protocol
patterns also have their own SDK dependencies and platform requirements.

Follow the chosen pattern's guide to export `OPENAI_API_KEY` securely. Do not put a
real key in a command, committed file, article, screenshot, or terminal recording.
The scripts read exported variables and do not automatically load `.env` files.

## Model verification and access

The default `gpt-6-astra` model ID, Responses endpoint, low/medium reasoning,
structured outputs, and function calling are documented in the
[official model reference](https://developers.openai.com/api/docs/models/gpt-6-astra)
(checked 2026-10-24). Account access and quotas are separate from a valid model ID.
No live model request is needed to validate installation or run the offline tests.

Request and output limits are not dollar caps; input and reasoning tokens may also
incur charges.

## Switch models

The model is configurable in all 21 optional implementations. You do not need to
edit their source files. This setting controls the example programs, independently
of the model selected for your Codex chat.

| Choice | Exact API model ID | Official reference |
| --- | --- | --- |
| Default | `gpt-6-astra` | [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra) |
| GPT-6.1 Sol | `gpt-6.1-sol` | [GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol) |

Use the complete API model ID, such as `gpt-6.1-sol`, rather than `6.1`. Both
models document Responses, structured outputs, function calling, and the low/medium
reasoning settings used here (checked 2026-10-25). Changing the model preserves the
pattern's existing reasoning effort, request limits, and output caps. It does not
automatically select the provider's default reasoning effort.

### Terminal setting

For macOS/Linux shells such as zsh or bash, set the model in the terminal where
you will run an optional example:

```bash
export OPENAI_MODEL=gpt-6.1-sol
```

For Windows PowerShell:

```powershell
$env:OPENAI_MODEL = "gpt-6.1-sol"
```

These commands only set an environment variable; they make no API request. Once
the SDK and key are configured, your chosen optional script will use that model.
For example, **deliberately running the following starts the billable Routing demo**:

```bash
python patterns/02-routing/openai_version/openai_router.py
```

The setting lasts for the current shell and its child processes. A new terminal
needs its own setting unless you configure it in your shell profile. Editing
`.env.example` or creating a `.env` file alone has no effect: these scripts do not
load dotenv files. The free local `app.py` examples do not use this variable.

### Python override and precedence

An explicit `model=` argument takes precedence over `OPENAI_MODEL`. This example
is **billable when executed**:

```python
from importlib import import_module

router = import_module("patterns.02-routing.openai_version.openai_router")
result = router.route_with_openai(
    "I was charged twice.", model="gpt-6.1-sol"
)
```

Selection order is: a non-empty explicit `model=` value, then a nonblank
`OPENAI_MODEL`, then the built-in `gpt-6-astra` default. When reusing a responder in
Patterns 08/09, set its `model=` at construction; that responder owns selection,
and the runner rejects supplying both a responder and a separate model argument.

### Switch back to Astra

In zsh/bash, choose Astra explicitly:

```bash
export OPENAI_MODEL=gpt-6-astra
```

Or remove the override to restore the built-in default:

```bash
unset OPENAI_MODEL
```

In PowerShell, use `$env:OPENAI_MODEL = "gpt-6-astra"`, or remove the override with
`Remove-Item Env:OPENAI_MODEL -ErrorAction SilentlyContinue`. An explicit Python
`model=` argument still wins, so omit it if you want the environment/default.

### Pattern 16: optional separate economy model

Resource-Aware Optimization can use a different model for its economy profile.
Its selection order is `economy_model=`, then `OPENAI_ECONOMY_MODEL`, then the
main selected model. To make both profiles follow `OPENAI_MODEL`, omit the Python
`economy_model=` argument and clear that separate environment override:

```bash
unset OPENAI_ECONOMY_MODEL
```

In PowerShell, use `Remove-Item Env:OPENAI_ECONOMY_MODEL -ErrorAction SilentlyContinue`.
Alternatively, deliberately set `OPENAI_ECONOMY_MODEL=gpt-6.1-sol` for the economy
profile; the same model-capability and billing requirements apply.

The offline HTTP contracts check the default and `OPENAI_MODEL=gpt-6.1-sol` paths
for every adapter without contacting a model endpoint. They verify configuration
and serialization, not live output quality, pricing, quotas, or account access.

## Per-pattern setup and request behavior

- [Prompt Chaining setup](../patterns/01-prompt-chaining/openai_version/README.md)
- [Routing setup](../patterns/02-routing/openai_version/README.md)
- [Parallelization setup](../patterns/03-parallelization/openai_version/README.md)
- [Reflection setup](../patterns/04-reflection/openai_version/README.md)
- [Tool Use setup](../patterns/05-tool-use/openai_version/README.md)
- [Planning setup](../patterns/06-planning/openai_version/README.md)
- [Multi-Agent Collaboration setup](../patterns/07-multi-agent-collaboration/openai_version/README.md)
- [Memory Management setup](../patterns/08-memory-management/openai_version/README.md)
- [Learning and Adaptation setup](../patterns/09-learning-and-adaptation/openai_version/README.md)
- [MCP + OpenAI setup](../patterns/10-model-context-protocol/openai_version/README.md)
- [Goal Setting and Monitoring setup](../patterns/11-goal-setting-and-monitoring/openai_version/README.md)
- [Exception Handling and Recovery setup](../patterns/12-exception-handling-and-recovery/openai_version/README.md)
- [Human-in-the-Loop setup](../patterns/13-human-in-the-loop/openai_version/README.md)
- [Knowledge Retrieval setup](../patterns/14-knowledge-retrieval/openai_version/README.md)
- [A2A + OpenAI setup](../patterns/15-inter-agent-communication/openai_version/README.md)
- [Resource-Aware Optimization setup](../patterns/16-resource-aware-optimization/openai_version/README.md)
- [Reasoning Techniques setup](../patterns/17-reasoning-techniques/openai_version/README.md)
- [Guardrails/Safety setup](../patterns/18-guardrails-safety/openai_version/README.md)
- [Evaluation and Monitoring setup](../patterns/19-evaluation-monitoring/openai_version/README.md)
- [Prioritization setup](../patterns/20-prioritization/openai_version/README.md)
- [Exploration and Discovery setup](../patterns/21-exploration-discovery/openai_version/README.md)

All use the official OpenAI Python SDK and the Responses API. The default model
is `gpt-6-astra` with low reasoning effort for Patterns 01–15 and 18–21. Pattern 16 uses low
for economy and medium for thorough, with an optional separate economy model.
Pattern 17 uses medium effort to propose arithmetic expressions for local checking.
Set `OPENAI_MODEL` to override the model,
or pass `model=` when calling the Python functions (which takes precedence).
Overrides must support Responses and the configured reasoning effort; Routing, Reflection, Planning, Multi-Agent Collaboration, Learning and Adaptation, Goal Setting and Monitoring, Exception Handling and Recovery, Human-in-the-Loop, Knowledge Retrieval, Inter-Agent Communication, Reasoning Techniques, Guardrails/Safety, Evaluation and Monitoring, Prioritization, and Exploration and Discovery
also require structured outputs; Tool Use and MCP require function calling. API usage is billed separately and requires access to the chosen model.
The examples make three API requests for a chain, one for a routing decision, and
up to three concurrent requests for parallel analysis. The parallel result is merged locally. Reflection makes up to six sequential
requests with its default budget of two revisions, stopping earlier on approval
or repeated drafts. Tool Use makes at most four model requests with its default
budget of three tool calls; its tools execute locally using simulated data. Planning
makes at most two model requests with its default one-replan budget and executes
its validated plan locally against a fictional catalog. Multi-Agent Collaboration
makes at most four sequential model requests for its supervisor, up to two
specialists, and writer. Memory Management makes one request per ordinary chat
turn, while explicit memory controls run locally; its interactive CLI defaults
to at most five model requests per run. Learning and Adaptation makes one request
per generated reply, with local feedback updates and a default five-attempt CLI
budget; it changes the application policy, not model weights. MCP allows at most
three model requests with its default two-tool budget; discovery and local
protocol calls do not incur API charges. Goal Setting and Monitoring makes at most
six requests with its default action budget, stopping on measured completion,
stalls, or its cooperative time deadline; ticket actions and monitoring are local.
Exception Handling and Recovery defaults to at most two model attempts with SDK
retries disabled, then a local rule when fallback is permitted. Lookup retries
and cached demo data are local; terminal model errors stop without model fallback.
Human-in-the-Loop makes at most one model attempt to create a pending draft; human
edits, approval, rejection, and simulated dispatch run locally without more requests.
Knowledge Retrieval uses free local BM25 retrieval and at most one model synthesis
request; no qualifying evidence means no model request. It uses no embedding API
or vector database. Citation validation checks source IDs/excerpts, not semantic
entailment of every generated claim. Inter-Agent Communication makes at most one
model attempt for a complete valid ticket in its CLI; discovery, missing-input
follow-ups, and task retrieval are local. The host owns protocol state and publishes
a validated report artifact; the model does not choose endpoints or execute actions.
Resource-Aware Optimization makes at most two model attempts for a query, subject to
a shared call/output-token allowance and cooperative deadline. It reserves caps
before each attempt, retains reservations on failure, and reuses exact session
cache hits. Output-token allowances exclude input charges and are not dollar caps.
Reasoning Techniques makes at most two model attempts, with up to three expression
candidates per attempt. Python checks arithmetic exactly, returns machine-recomputed
calculations, and sends rejected-candidate observations back for one correction.
It does not expose private model reasoning or claim impossibility from model failure.
Guardrails/Safety makes at most one action-proposal request after input and ownership
checks. Host code restricts actions and order targets, validates outgoing facts, and
never executes a write. Demo redaction/override patterns are limited examples, not
a complete moderation, authentication, or prompt-injection defense. Evaluation and
Monitoring defaults to three sequential routing requests, leaving explicit incomplete
coverage on its eight-case dataset; `--max-cases 8` allows a full run. Reference
labels stay in the host grader, SDK retries are disabled, and provider errors stop
further calls. Gates and rolling alerts run locally; known token totals are not dollar caps.
Prioritization makes at most one request to rank the host-eligible task set. Python
validates the exact ID permutation, preserves hard constraints, and uses an explicit
rule fallback on model failure. No eligible work or a zero model budget means no
request; fictional work-minute budgets do not cap model charges. Exploration and
Discovery allows at most three model proposals, only when several affordable
experiments are offered. The host validates IDs, runs a fictional lab, and records
evidence; failed model proposals disable further model calls and use local rules.
Its six-experiment/eight-cost-unit defaults are simulated lab limits, not API dollar caps.

The SDK is installed separately using each `openai_version/requirements.txt`,
so local-only users do not need it. Scripts read exported environment variables;
they do **not** automatically load `.env` files. The setup guides include the export step.

Model migration reference: [OpenAI GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model).
The migration removes `temperature=0`, uses low reasoning effort, and makes model
selection configurable. Offline tests verify request construction and application
behavior; they do not measure live model quality, latency, or account access.
