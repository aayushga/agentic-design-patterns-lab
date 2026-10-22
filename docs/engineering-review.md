# Repository engineering review — 2026-10-22

Reviewed main commit `be9ea12077e8dc0e51c734c04815701200b9c06c` after all 21 patterns
were merged. Scope: every local implementation and optional adapter, protocol
servers/clients, fixtures, tests, dependency declarations, documentation, and CI.
No paid API calls were made. All measurements discussed below are offline tests,
SDK HTTP mocks, static analysis, or public dependency metadata queries.

## Assessment

The repository is a useful learning lab with explicit schemas, allowlisted actions,
fictional fixtures, independent examples, and substantial offline regression coverage.
It should not be deployed unchanged as a production agent service: authentication,
durable workflows, real write safety, concurrency, production data governance, and
representative quality evaluation are intentionally absent. Those are architectural
requirements for a deployment, not features to simulate with more prompt text.

The baseline passed 1,394 tests. Application line coverage was 87.8% (reported as
88% with integer rounding), excluding tests/examples; lower coverage was largely
interactive/CLI error paths. A limited tracked-text/history credential-pattern scan
found no matches. This is not an exhaustive secret audit. Bandit reported no findings;
Ruff found three unused imports. Passing scanners did not catch the logic bugs below.

## Reproduced correctness findings and fixes

| Priority | Finding | Concrete behavior before the fix | Resolution |
| --- | --- | --- | --- |
| High | Mutable reflection approval | Reviser changed a rejected critique, returned the same draft, and obtained `approved=True` with `no_progress` | Isolate reviewer, reviser, and recorded feedback snapshots |
| High | Tool budget owned by callback history | Clearing history let a one-call budget execute three tools and return zero recorded observations | Give deciders copied history and snapshot executed arguments |
| High | Mutable planning constraints | Planner changed input budget from 1 to 1,000 USD; a 500 USD plan passed validation | Freeze host request facts |
| Medium | Invalid/rollback clocks | NaN prevented expiry and allowed an approved simulated dispatch | Validate every clock reading; fail closed and disable faulty stateful controllers |
| Medium | NaN quality gates | Comparisons against NaN could fall through to a passing decision | Reject invalid gate metrics and comparisons |
| Medium | Regression boundary arithmetic | A 19/20 result against 20/20 incorrectly crossed a five-percentage-point tolerance through float rounding | Absorb only rounding noise at the bounded-case threshold |
| Medium | SDK request limits incomplete | Early adapters inherited retries and leaked clients; several lacked output/storage settings | Explicit retries/timeouts/caps, lifecycle cleanup, bounded inputs, and real-SDK HTTP tests |
| Medium | Stale dependency resolution | Existing environment carried advisories in six packages | Central patched floors, strict installed-dependency audit, update proposals, and platform documentation |
| Medium | Private local state easy to commit | Only `.env` was ignored; `.env.local` and persisted memory databases were not | Ignore credential variants, databases, editor metadata, and verification artifacts |
| Maintenance | Repeated setup/CI inventories | Long duplicated install/demo lists could omit a pattern or drift | Shared requirements, discovered standalone suites/demos, and repository-contract tests |

Fix PRs remain open for human review:

- [Host-owned state and time controls — PR #28](https://github.com/aayushga/agentic-design-patterns-lab/pull/28)
- [Bounded SDK integrations and real HTTP contracts — PR #29](https://github.com/aayushga/agentic-design-patterns-lab/pull/29)
- Repository quality, dependency policy, and this report are the third review change.

The PRs are independently based on the reviewed main. Merge all three to obtain
the complete set; a final combined validation checks that they work together.
No PR is merged automatically by this review.

## Architectural review across all patterns

| Patterns | What is sound | Production boundary / remaining limitation |
| --- | --- | --- |
| 01–03: chain, routing, parallelization | Explicit step handoffs, known-route fallback, partial branch results | Keyword rules are demonstrations; model confidence labels are not calibrated probabilities; async deadlines are cooperative |
| 04–07: reflection, tools, planning, collaboration | Bounded loops, local tool allowlists, catalog validation, exact excerpt evidence | A critic can still make a semantic mistake; specialist excerpts do not prove assessments; generated writer text needs independent review |
| 08–09: memory, adaptation | Explicit persistence commands, version invalidation, isolated contexts, single-use feedback | User IDs are not authentication; SQLite is plaintext/single-thread oriented; feedback needs provenance and abuse controls |
| 10: MCP | Fixed local server command, real protocol lifecycle, tool allowlist, bounded discovery | A production server needs resource/output bounds, schema trust policy, auth, and isolation; do not accept arbitrary model-selected servers |
| 11–12: goals, recovery | Host-measured progress, bounded steps/stalls, safe retry classification, explicit degradation | Cooperative timeouts do not interrupt arbitrary blocking Python; real write retries require idempotency and reconciliation |
| 13: human review | Revision-specific approval, expiry, immutable records, single simulated dispatch | Reviewer names are labels; real identity, durable approvals, transactional outbox, and external idempotency remain necessary |
| 14: retrieval | Current-source filtering, bounded context, exact citation provenance, abstention | No document ACLs or semantic entailment proof; adversarial corpus tests and source governance are needed |
| 15: A2A | Fixed local endpoint, real task protocol, validated report artifact, cleanup | The ASGI demo has no public-service authentication, tenant isolation, durable task store, or cancellation implementation |
| 16–18: resources, reasoning, guards | Conservative reservations, exact arithmetic verification, host-bound read actions | Output allowance is not a dollar cap; regex guards/redaction are incomplete; real tools need authorization and safety beyond prompts |
| 19–21: evaluation, prioritization, discovery | Explicit denominators/unknowns, feasible task selection, host-created experimental evidence | Small synthetic datasets are not benchmarks; soft deadlines/aging do not guarantee fairness; deterministic discovery is not real research |

Standaloneness is intentional: keep each educational pattern easy to read and run.
A large shared agent framework or a blanket rewrite would obscure the patterns.
Share installation, verification, and deployment adapters where they provide clear
value; keep domain control flow visible. Python callbacks remain trusted code even
when copied/frozen inputs protect host invariants against accidental mutation.

## Validation and continuous checks

- PR #28: 1,430 tests, including 36 new regressions; all 63 free demos passed.
- PR #29: 1,436 tests, including 19 validation/lifecycle regressions and 23 real-SDK
  HTTP contracts; repeated successfully with SDK 2.54.0 and updated protocol dependencies.
- Real-SDK mocks cover every adapter, sync/async clients, tool transcript correlation,
  client cleanup, retry suppression, pending human review, partial coverage, and host evidence.
- Test collection and execution both block socket connections and remove model credentials.
  The guard is restored after the session for programmatic pytest users. Example verification removes OpenAI
  environment variables and blocks sockets in each launched local demo process.
  The fixed MCP subprocess is a read-only local protocol server, not a general sandbox.
- Python 3.10/3.11/3.12/3.14 CI checks the supported pattern subsets independently.
  SDK CI covers minimum and latest compatible 2.x on Python 3.12.
- Quality CI measures application coverage with an 85% floor, runs static checks,
  validates installation, and audits the full installed resolution. Advisory metadata
  queries require network access; no model endpoint is involved.
- PR #30: 1,406 offline tests, all 21 standalone suites, and 63 local demos passed.
- Combined review tree: 1,484 tests passed, 87.9% application coverage, and 63 local
  demos passed; the three PRs combine without merge conflicts.
- Dependabot proposes weekly dependency/action updates. No automatic merge is configured.

See [dependency policy](dependencies.md) for the patched floors and Intel macOS
cryptography-wheel limitation. The original user environment is not silently
upgraded or declared clean. Fully patched resolution is validated on Linux CI.

## Recommended separately before any production deployment

1. Define one concrete use case and threat model; turn it into a small service
   instead of exposing all 21 learning demos. Authenticate users/reviewers and bind
   authorization to every data read, tool call, and persisted task.
2. Add durable workflow state, transactional writes/outbox, idempotency keys,
   optimistic concurrency, leases, retention/deletion, and crash/retry recovery tests.
3. Build representative held-out evals with adversarial/injection cases, independently
   reviewed labels, repeated measurements, and quality/cost/latency acceptance targets.
   Offline mocks verify contracts, not live model behavior. Any paid evaluation
   needs separate explicit authorization and a real monetary budget.
4. Add structured tracing with redaction, access control, token/input cost accounting,
   operational SLOs, cancellation, concurrency limits, and a hard execution boundary
   for untrusted/long-running tools. Avoid logging customer prompts by default.
5. Create per-platform hashed deployment locks/SBOMs and rebuild images on advisories.
   Validate an SDK 3.x migration separately; do not widen compatible major bounds
   without the HTTP contracts and application tests.
6. Enable private vulnerability reporting, repository secret scanning/push protection,
   and required reviews/checks for the new jobs in branch protection. Current `main`
   is protected, but individual protection/security settings were not changed here.

These recommendations are deliberately separate from the focused learning-lab fixes.
