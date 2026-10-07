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
- [ ] 05. Tool Use
- [ ] 06. Planning
- [ ] 07. Multi-Agent Collaboration
- [ ] 08. Memory Management
- [ ] 09. Learning and Adaptation
- [ ] 10. Model Context Protocol (MCP)
- [ ] 11. Goal Setting and Monitoring
- [ ] 12. Exception Handling and Recovery
- [ ] 13. Human-in-the-Loop
- [ ] 14. Knowledge Retrieval (RAG)
- [ ] 15. Inter-Agent Communication (A2A)
- [ ] 16. Resource-Aware Optimization
- [ ] 17. Reasoning Techniques
- [ ] 18. Guardrails/Safety Patterns
- [ ] 19. Evaluation and Monitoring
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

Each includes a default local implementation, basic and advanced examples, an
optional OpenAI implementation, and offline tests. Pattern 05: Tool Use is next.

## Run and Test

Use Python 3.10 or newer. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/01-prompt-chaining/requirements.txt -r patterns/02-routing/requirements.txt -r patterns/03-parallelization/requirements.txt -r patterns/04-reflection/requirements.txt
python -m pytest
python patterns/01-prompt-chaining/app.py
python patterns/02-routing/app.py
python patterns/03-parallelization/app.py
python patterns/04-reflection/app.py
```

The default examples use only the Python standard library. The test suite uses
pytest, fake API responses, and blocks network connections; no API key is needed.
You can also run `python -m pytest` from any pattern folder.

## GitHub Actions

[Python tests](https://github.com/aayushga/agentic-design-patterns-lab/actions/workflows/tests.yml)
runs automatically on pushes and pull requests, using GitHub-hosted Ubuntu runners
with Python 3.10, 3.12, and 3.14. It runs the combined suite, each pattern's suite
independently, and all local examples. No OpenAI API key or SDK is required, and
the tests make no live API calls.

Review changes in a pull request's **Files changed** tab and results in **Checks**.
Full logs are available under **Actions → Python tests**. Once the workflow is on
the default branch, you can also start it manually with **Run workflow**.
No local editor is required for review.

## Optional OpenAI Versions

- [Prompt Chaining setup](patterns/01-prompt-chaining/openai_version/README.md)
- [Routing setup](patterns/02-routing/openai_version/README.md)
- [Parallelization setup](patterns/03-parallelization/openai_version/README.md)
- [Reflection setup](patterns/04-reflection/openai_version/README.md)

All use the official OpenAI Python SDK and the Responses API. The default model
is `gpt-6-astra` with low reasoning effort. Set `OPENAI_MODEL` to override the model,
or pass `model=` when calling the Python functions (which takes precedence).
Overrides must support Responses and low reasoning effort; Routing and Reflection
also require structured outputs. API usage is billed separately and requires access to the chosen model.
The examples make three API requests for a chain, one for a routing decision, and
up to three concurrent requests for parallel analysis. The parallel result is merged locally. Reflection makes up to six sequential
requests with its default budget of two revisions, stopping earlier on approval
or repeated drafts.

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
