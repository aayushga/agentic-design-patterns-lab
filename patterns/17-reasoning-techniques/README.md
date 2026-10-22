# Pattern 17: Reasoning Techniques

Use four supplied numbers exactly once, with binary `+`, `-`, `*`, `/`, and parentheses,
to reach a target (24 by default). This small problem has a checkable answer, making
it useful for learning reasoning techniques without trusting a plausible explanation.

This is an original exercise inspired by Chapter 17 of Antonio Gulli's *Agentic
Design Patterns*. It demonstrates **arithmetic decomposition**, **search over
alternative expressions**, and an optional **propose → verify → revise** model loop.
It does not reproduce the book's Deep Research implementation or implement every
technique in the chapter.

## What the examples teach

| Approach | What happens | What establishes success |
| --- | --- | --- |
| Basic verification | Decompose a proposed expression into arithmetic operations | Exact calculation and input-number checks |
| Bounded search | Combine pairs of values, explore alternatives, and backtrack | A found expression passes the separate verifier |
| Optional model loop | Propose up to three expressions, check them, optionally revise once | A candidate passes the same local verifier |

The search is a deterministic symbolic illustration of exploring a tree of
alternatives, **not an LLM Tree-of-Thought implementation**. The model loop borrows
the action/observation principle: it receives checker observations before a correction.
It is not a general ReAct agent or a Responses tool-calling implementation. There
is no voting, debate, or claim that sampled proposals are independent.

Pattern 04 refines prose using critiques; Pattern 06 validates/exercises a plan;
Pattern 16 allocates resources. Here the answer itself has an exact mathematical
verifier, and alternatives can be searched or revised against that verifier.

## Run locally for free

Python 3.10+; from the repository root:

```bash
python -m pip install -r patterns/17-reasoning-techniques/requirements.txt
python patterns/17-reasoning-techniques/app.py
python patterns/17-reasoning-techniques/examples/basic_example.py
python patterns/17-reasoning-techniques/examples/advanced_example.py
python -m pytest patterns/17-reasoning-techniques/tests -q
```

Local code uses only the Python standard library. Pytest is needed for tests.
No OpenAI package, API key, external service, or API charge is required. You can
also run `python -m pytest` from this pattern folder.

The basic example checks `((6+4)-2)*3` for the numbers `2,3,4,6`. Its JSON report
contains the expression, validity, value, error (if any), and these calculation steps:

```text
6 + 4 = 10
10 - 2 = 8
8 * 3 = 24
valid: true
```

The advanced example starts with an incorrect candidate, then searches for a valid
alternative. Representative output:

```text
Initial proposal: (8-3)*(8-3) = 25; valid=False; error=wrong_target
Alternative search: solved; expression=(8/(3-(8/3))); states=345
  8 / 3 = 8/3
  3 - (8/3) = 1/3
  8 / (1/3) = 24
Tiny search budget: budget_exhausted; reason=state_budget; states=1
Exhaustive search for 1,1,1,1: no_solution; reason=search_exhausted; states=24
```

These are **machine-recomputed calculations**, not a transcript of a model's private
reasoning. Fractional intermediates use `fractions.Fraction`; the target comparison
is exact and does not depend on floating-point rounding.

`app.py` prints the full structured search result: puzzle, method, status, solution,
checks/calculations, explored-state count, model-attempt count, and stop reason.

## Search and verification limits

- A puzzle contains exactly four integers from 1 to 12, including duplicates. Targets
  are integers from 1 to 100. Every number must appear with its original multiplicity.
- The verifier parses expressions using `ast`, then interprets only allowed integer
  leaves and binary arithmetic. It never uses `eval`, `exec`, imports, shell calls,
  function calls, or attribute lookup. Powers, concatenation of numbers, unary
  operators, floats, booleans, and division by zero cannot pass verification.
- Expressions are at most 120 **raw characters**, including whitespace, and 32 AST
  nodes. The number/target constraints are checked independently of the proposed text.
- Search combines disjoint source terms, so each generated expression uses each input
  occurrence exactly once. It tries both subtraction/division orders, skips zero
  divisors, and retains one representative of equivalent pair results.
- Memoization uses the sorted multiset of exact intermediate values: future reachable
  values depend on those values, not on which equivalent expression produced them.
  This prunes duplicate states without eliminating a necessary arithmetic alternative.
- The default budget is 10000 distinct states (configurable from 1 to 100000). Four
  inputs imply at most three combination levels. Search returns the first solution,
  without claiming the shortest or most readable expression.
- `solved` includes a separately verified expression. `no_solution` means all reachable
  states under these specific arithmetic rules were exhausted. `budget_exhausted`
  means search stopped early; it does **not** prove that no solution exists.
- Success in this arithmetic domain does not establish general reasoning ability or
  factual correctness in open-ended tasks. More search or model attempts do not
  guarantee success; input rules and the verifier define what is being checked.

## Optional OpenAI version

[Setup and usage](openai_version/README.md). Astra proposes expression candidates;
the host determines arithmetic validity and stopping. It can send wrong-answer
observations back for one correction, without running a hidden local solver as a
fallback or accepting an unverified model claim of impossibility.

Tests cover exact fractions, input multiplicities, disallowed syntax, division by
zero, search bounds, impossible puzzles, permutations, and fake model correction,
refusal/incomplete output, request limits, configuration, and cleanup.

Next: **Pattern 18 — Guardrails/Safety Patterns**.
