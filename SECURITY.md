# Security and intended use

This repository is an educational lab, not a deployable multi-user agent service.
Local examples use fictional data. Optional model examples make billable requests
only when deliberately run with credentials; committed tests do not call real APIs.
The maintained code is on `main`; review the current dependency constraints before
reusing it. Passing tests and vulnerability scans are not security certification.

## Credentials and private data

Export keys locally; keep them out of source, prompts, screenshots, logs, and PRs.
`.env*` files are ignored except the blank `.env.example` templates. SQLite state,
coverage output, and editor metadata are also ignored. Ignoring a file does not
remove it from earlier commits or encrypt it. Rotate an exposed key immediately
and remove it from history using an appropriate recovery process.

Memory user/session IDs and reviewer names are caller-supplied namespaces/audit
labels, not authentication. SQLite preferences are plaintext. JSONL may include
sensitive labels/metadata even when raw prompts are omitted. Use fictional data
for the demos; define access, encryption, retention, and deletion before real use.

## Agent boundaries

Schemas and allowlists constrain shape and actions, not the truth of every generated
sentence. Citation checks establish provenance, not semantic entailment. Regex
redaction and prompt-injection examples are incomplete. Trusted injected Python
callbacks can run arbitrary Python; immutable inputs/copies are not a code sandbox.

A real service needs authenticated identities, authorization at every data/tool
boundary, safe external-tool adapters, durable state/outboxes, idempotent writes,
concurrency control, measured budgets, and task-specific safety/quality evaluation.
Never expose the local MCP/A2A demos directly as unauthenticated public services.

## Dependency hygiene and reporting

See [dependency policy](docs/dependencies.md) and the [engineering review](docs/engineering-review.md).
GitHub Actions queries public vulnerability metadata and checks the installed
resolution. Dependabot proposes updates after its configuration is merged; updates
are not merged automatically. Install constraints are not a reproducible deployment
lockfile; create platform-specific hashed locks for an actual deployed application.

Report suspected vulnerabilities through GitHub's private vulnerability-reporting
facility when enabled. Maintainers should enable it under repository Security.
Do not post credentials, private customer data, or weaponized exploit details in
public issues. Public issues are appropriate for non-sensitive bugs and documentation.
