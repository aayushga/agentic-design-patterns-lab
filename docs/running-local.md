# Running local examples and tests

Use Python 3.11 or newer for the full lab (the MCP SDK v2 requirement).
Read the [Intel macOS dependency note](dependencies.md#intel-macos-limitation)
before a full binary-only install on that platform; local standard-library patterns
do not require the affected protocol dependency.
Patterns 01–09 and 11–21 also support Python 3.10. From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade 'pip>=26.2,<27'
python -m pip install --only-binary=:all: -r requirements.txt
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
python patterns/20-prioritization/app.py
python patterns/21-exploration-discovery/app.py
```

Patterns 01–09, 11–14, and 16–21 use only the Python standard library for local examples.
Pattern 10 uses the free official MCP SDK and local stdio subprocesses. Pattern 15
uses the free official A2A SDK and in-memory HTTP transport. The test suite uses
pytest, fake API responses, and blocks network connections; no API key is needed.
You can also run `python -m pytest` from any pattern folder.

## GitHub Actions

[Python tests](https://github.com/aayushga/agentic-design-patterns-lab/actions/workflows/tests.yml)
runs automatically on pushes and pull requests, using GitHub-hosted Ubuntu runners
with Python 3.10, 3.11, 3.12, and 3.14. It runs the combined suite, each pattern's
suite independently, and local examples. Python 3.10 covers Patterns 01–09 and 11–21; the
newer versions also run the real MCP protocol tests and demos. No OpenAI API key
or SDK is required, and the tests make no live API calls.

The [Repository quality workflow](../.github/workflows/quality.yml) adds static checks,
application coverage, installation checks, and an installed-dependency audit.
Standalone suites and local demos are discovered automatically; demo verification
removes OpenAI variables and blocks socket connections. Dependency advisory checks
use public metadata and require no model API key.

Review changes in a pull request's **Files changed** tab and results in **Checks**.
Full logs are available under **Actions → Python tests**. Once the workflow is on
the default branch, you can also start it manually with **Run workflow**.
No local editor is required for review.
