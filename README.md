# Agentic Design Patterns Lab

A hands-on, portfolio-ready lab for implementing **agentic AI design patterns** with clean, practical Python examples.

This repository is focused on:
- Learning core agentic patterns by building them from scratch
- Keeping implementations beginner-friendly and easy to run locally
- Demonstrating software engineering hygiene (tests, structure, docs)
- Showcasing production-lean thinking without unnecessary complexity

## What You'll Find in Each Pattern

Each pattern includes:
- Clear explanation of the design pattern
- When and why to use it
- Minimal runnable Python implementation
- Basic example
- Realistic example
- Unit tests
- No external API dependency (when possible)

## Pattern Roadmap (21 Patterns)

- [x] 01. Prompt Chaining
- [x] 02. Routing
- [x] 03. Parallelization
- [x] 04. Reflection
- [x] 05. Tool Use
- [x] 06. Planning
- [x] 07. Multi-Agent Collaboration
- [x] 08. Memory Management
- [x] 09. Learning and Adaptation
- [x] 10. Model Context Protocol (MCP)
- [x] 11. Goal Setting and Monitoring
- [x] 12. Exception Handling and Recovery
- [x] 13. Human-in-the-Loop
- [x] 14. Knowledge Retrieval (RAG)
- [x] 15. Inter-Agent Communication (A2A)
- [x] 16. Resource-Aware Optimization
- [x] 17. Reasoning Techniques
- [x] 18. Guardrails/Safety Patterns
- [x] 19. Evaluation and Monitoring
- [ ] 20. Prioritization
- [ ] 21. Exploration and Discovery

The roadmap follows Antonio Gulli's *Agentic Design Patterns: A Hands-On Guide to
Building Intelligent Systems*. Implementations are original, simplified Python
exercises inspired by the chapters. ReAct, self-consistency, and related techniques
can be explored within the relevant chapters instead of replacing the book's sequence.

## Current Progress

- [Pattern 01: Prompt Chaining](patterns/01-prompt-chaining/): sequential summary,
  theme extraction, and structured response.
- [Pattern 02: Routing](patterns/02-routing/): intent classification and dispatch
  to billing, support, sales, or a fallback handler.
- [Pattern 03: Parallelization](patterns/03-parallelization/): concurrent ticket
  analyses, followed by a local merge with per-task failure handling.

- [Pattern 04: Reflection](patterns/04-reflection/): a support-reply draft,
  critique, and revision loop with explicit stopping conditions.
- [Pattern 05: Tool Use](patterns/05-tool-use/): validated function calls,
  observations, and dependent order lookup and calculation.
- [Pattern 06: Planning](patterns/06-planning/): an explicit offsite plan,
  constraint validation, simulated execution, and bounded replanning.
- [Pattern 07: Multi-Agent Collaboration](patterns/07-multi-agent-collaboration/):
  supervisor delegation, specialist handoffs, and a combined support reply.
- [Pattern 08: Memory Management](patterns/08-memory-management/): bounded chat
  history, session state, and explicit SQLite preferences across sessions.
- [Pattern 09: Learning and Adaptation](patterns/09-learning-and-adaptation/):
  explicit feedback updates a contextual reply-strategy policy.
- [Pattern 10: Model Context Protocol](patterns/10-model-context-protocol/): real
  local MCP discovery, tools, resources, prompts, and an optional model bridge.

- [Pattern 11: Goal Setting and Monitoring](patterns/11-goal-setting-and-monitoring/):
  fixed triage goals, measured progress, adaptation, and bounded stopping.

- [Pattern 12: Exception Handling and Recovery](patterns/12-exception-handling-and-recovery/):
  classified failures, bounded retries, validated fallbacks, and honest degradation.

- [Pattern 13: Human-in-the-Loop](patterns/13-human-in-the-loop/):
  human review, revision-bound approval, edits, rejection, and simulated dispatch.

- [Pattern 14: Knowledge Retrieval (RAG)](patterns/14-knowledge-retrieval/):
  paragraph retrieval, bounded evidence, source citations, and abstention.

- [Pattern 15: Inter-Agent Communication (A2A)](patterns/15-inter-agent-communication/):
  Agent Card discovery, real JSON-RPC delegation, resumable tasks, and result artifacts.

- [Pattern 16: Resource-Aware Optimization](patterns/16-resource-aware-optimization/):
  response-profile selection, conservative resource reservations, cache reuse, and bounded fallback.

- [Pattern 17: Reasoning Techniques](patterns/17-reasoning-techniques/):
  exact arithmetic verification, bounded search over alternatives, and model proposal correction.

- [Pattern 18: Guardrails/Safety Patterns](patterns/18-guardrails-safety/):
  layered input screening, redaction, host authorization, action limits, and output validation.

- [Pattern 19: Evaluation and Monitoring](patterns/19-evaluation-monitoring/):
  labeled cases, exact-match grading, honest coverage/usage, quality gates, and rolling alerts.

Each includes a default local implementation, basic and advanced examples, an
optional OpenAI implementation, and offline tests. Pattern 20: Prioritization is next.

## Run and Test

Use Python 3.11 or newer for the full lab (the MCP SDK v2 requirement).
Patterns 01–09 and 11–19 also support Python 3.10. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --only-binary=:all: -r patterns/01-prompt-chaining/requirements.txt -r patterns/02-routing/requirements.txt -r patterns/03-parallelization/requirements.txt -r patterns/04-reflection/requirements.txt -r patterns/05-tool-use/requirements.txt -r patterns/06-planning/requirements.txt -r patterns/07-multi-agent-collaboration/requirements.txt -r patterns/08-memory-management/requirements.txt -r patterns/09-learning-and-adaptation/requirements.txt -r patterns/10-model-context-protocol/requirements.txt -r patterns/11-goal-setting-and-monitoring/requirements.txt -r patterns/12-exception-handling-and-recovery/requirements.txt -r patterns/13-human-in-the-loop/requirements.txt -r patterns/14-knowledge-retrieval/requirements.txt -r patterns/15-inter-agent-communication/requirements.txt -r patterns/16-resource-aware-optimization/requirements.txt -r patterns/17-reasoning-techniques/requirements.txt -r patterns/18-guardrails-safety/requirements.txt -r patterns/19-evaluation-monitoring/requirements.txt
python -m pytest
python patterns/01-prompt-chaining/app.py
python patterns/02-routing/app.py
python patterns/03-parallelization/app.py
python patterns/04-reflection/app.py
python patterns/05-tool-use/app.py
python patterns/06-planning/app.py
python patterns/07-multi-agent-collaboration/app.py
python patterns/08-memory-management/app.py
python patterns/09-learning-and-adaptation/app.py
python patterns/10-model-context-protocol/app.py
python patterns/11-goal-setting-and-monitoring/app.py
python patterns/12-exception-handling-and-recovery/app.py
python patterns/13-human-in-the-loop/app.py
python patterns/14-knowledge-retrieval/app.py
python patterns/15-inter-agent-communication/app.py
python patterns/16-resource-aware-optimization/app.py
python patterns/17-reasoning-techniques/app.py
python patterns/18-guardrails-safety/app.py
python patterns/19-evaluation-monitoring/app.py
```

Patterns 01–09, 11–14, and 16–19 use only the Python standard library for local examples.
Pattern 10 uses the free official MCP SDK and local stdio subprocesses. Pattern 15
uses the free official A2A SDK and in-memory HTTP transport. The test suite uses
pytest, fake API responses, and blocks network connections; no API key is needed.
You can also run `python -m pytest` from any pattern folder.

## GitHub Actions

[Python tests](https://github.com/aayushga/agentic-design-patterns-lab/actions/workflows/tests.yml)
runs automatically on pushes and pull requests, using GitHub-hosted Ubuntu runners
with Python 3.10, 3.11, 3.12, and 3.14. It runs the combined suite, each pattern's
suite independently, and local examples. Python 3.10 covers Patterns 01–09 and 11–19; the
newer versions also run the real MCP protocol tests and demos. No OpenAI API key
or SDK is required, and the tests make no live API calls.

Review changes in a pull request's **Files changed** tab and results in **Checks**.
Full logs are available under **Actions → Python tests**. Once the workflow is on
the default branch, you can also start it manually with **Run workflow**.
No local editor is required for review.

## Optional OpenAI Versions

- [Prompt Chaining setup](patterns/01-prompt-chaining/openai_version/README.md)
- [Routing setup](patterns/02-routing/openai_version/README.md)
- [Parallelization setup](patterns/03-parallelization/openai_version/README.md)
- [Reflection setup](patterns/04-reflection/openai_version/README.md)
- [Tool Use setup](patterns/05-tool-use/openai_version/README.md)
- [Planning setup](patterns/06-planning/openai_version/README.md)
- [Multi-Agent Collaboration setup](patterns/07-multi-agent-collaboration/openai_version/README.md)
- [Memory Management setup](patterns/08-memory-management/openai_version/README.md)
- [Learning and Adaptation setup](patterns/09-learning-and-adaptation/openai_version/README.md)
- [MCP + OpenAI setup](patterns/10-model-context-protocol/openai_version/README.md)
- [Goal Setting and Monitoring setup](patterns/11-goal-setting-and-monitoring/openai_version/README.md)
- [Exception Handling and Recovery setup](patterns/12-exception-handling-and-recovery/openai_version/README.md)
- [Human-in-the-Loop setup](patterns/13-human-in-the-loop/openai_version/README.md)
- [Knowledge Retrieval setup](patterns/14-knowledge-retrieval/openai_version/README.md)
- [A2A + OpenAI setup](patterns/15-inter-agent-communication/openai_version/README.md)
- [Resource-Aware Optimization setup](patterns/16-resource-aware-optimization/openai_version/README.md)
- [Reasoning Techniques setup](patterns/17-reasoning-techniques/openai_version/README.md)
- [Guardrails/Safety setup](patterns/18-guardrails-safety/openai_version/README.md)
- [Evaluation and Monitoring setup](patterns/19-evaluation-monitoring/openai_version/README.md)

All use the official OpenAI Python SDK and the Responses API. The default model
is `gpt-6-astra` with low reasoning effort for Patterns 01–15 and 18–19. Pattern 16 uses low
for economy and medium for thorough, with an optional separate economy model.
Pattern 17 uses medium effort to propose arithmetic expressions for local checking.
Set `OPENAI_MODEL` to override the model,
or pass `model=` when calling the Python functions (which takes precedence).
Overrides must support Responses and the configured reasoning effort; Routing, Reflection, Planning, Multi-Agent Collaboration, Learning and Adaptation, Goal Setting and Monitoring, Exception Handling and Recovery, Human-in-the-Loop, Knowledge Retrieval, Inter-Agent Communication, Reasoning Techniques, Guardrails/Safety, and Evaluation and Monitoring
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

The SDK is installed separately using each `openai_version/requirements.txt`,
so local-only users do not need it. Scripts read exported environment variables;
they do **not** automatically load `.env` files. The setup guides include the export step.

Model migration reference: [OpenAI GPT-6 guide](https://developers.openai.com/api/docs/guides/latest-model).
The migration removes `temperature=0`, uses low reasoning effort, and makes model
selection configurable. Offline tests verify request construction and application
behavior; they do not measure live model quality, latency, or account access.

## Who This Is For

- Engineers building practical AI systems
- Learners exploring agent architecture fundamentals
- Recruiters and hiring teams evaluating implementation quality quickly
