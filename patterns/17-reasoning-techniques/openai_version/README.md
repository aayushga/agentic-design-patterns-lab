# Optional OpenAI proposals with exact verification

The official OpenAI Python SDK and Responses API propose arithmetic expressions.
The host parses each candidate and checks it with exact fractions, including use
of all four input numbers. It returns a structured result with verified calculations.

A first batch can contain up to three candidates. If every candidate fails its
arithmetic check, the host can make one correction request with the checked
expressions, observed values, errors, and arithmetic operations. A valid candidate
stops the loop immediately. This is a bounded propose/check/revise exercise, not
an unrestricted autonomous agent.

## Setup

Python 3.10+; from the repository root:

```bash
python -m pip install --only-binary=:all: -r patterns/17-reasoning-techniques/openai_version/requirements.txt
export OPENAI_API_KEY="your-api-key"
export OPENAI_MODEL="gpt-6-astra"
python patterns/17-reasoning-techniques/openai_version/openai_reasoning.py
```

For a different puzzle or a single-attempt limit:

```bash
python patterns/17-reasoning-techniques/openai_version/openai_reasoning.py --numbers 2 3 4 6 --target 24 --max-attempts 1
```

`.env.example` documents settings; scripts do not automatically load `.env`. A missing
`OPENAI_API_KEY` gives a clear error before SDK import/client creation. Puzzle and
attempt limits are validated first. Explicit `model=` overrides `OPENAI_MODEL`,
which overrides `gpt-6-astra`. Overrides must support Responses, medium reasoning
effort, and strict structured outputs.

## Output and stopping

A successful result has `status: solved`, a verified solution, the local calculation
steps, and `model_attempts` of one or two. For example, `8/(3-8/3)` is verified as
exactly 24 for inputs `3,3,8,8`, regardless of any model explanation.

- All candidates fail within the attempt limit: `unverified`, reason `model_budget`.
- The model returns an empty candidate list: `unverified`, reason `model_abstained`;
  this stops without another request and is not proof of impossibility.
- Request error, refusal/empty or malformed output, or non-completed response:
  `failed` with a safe stop reason. These do not trigger another billable attempt.
- No model result is labeled `no_solution`; only the separate local exhaustive search
  can establish that status under the puzzle's arithmetic rules.

The host does not run the local search as a fallback, ask a model to judge its own
answer, or accept agreement between candidates as proof. Up to six checks are
possible across two batches. Repeated candidates carry no extra authority.

## Cost and model behavior

**The optional version is billable.** The default budget is at most two sequential
model attempts, with a 2000-generated-token cap per request, medium reasoning effort,
a 30-second SDK timeout, disabled SDK retries, and `store=False`. Generated-token
caps include reasoning tokens; they are not a total dollar limit and exclude input
charges. A cap can cause incomplete output or no visible candidate. A timeout can
still incur usage; no exact total wall-clock bound is claimed.

The SDK client closes on exit. The second request is stateless and includes only
the puzzle and bounded checker observations, not provider reasoning items. The
response text is at most 2000 raw characters before JSON parsing; schema/host checks
limit it to three expressions of at most 120 raw characters each.

The prompt asks for final expressions only, following [official reasoning-model
prompting guidance](https://developers.openai.com/api/docs/guides/reasoning-best-practices).
Displayed calculation steps are constructed by Python, not extracted private
chain-of-thought. [Structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
constrain the response shape; the arithmetic verifier establishes correctness for
this puzzle. The [Astra model reference](https://developers.openai.com/api/docs/models/gpt-6-astra)
documents supported reasoning effort and API features.

All tests use fake responses and require no OpenAI SDK or API key. They verify
host behavior and request construction, not live model success rate, account
access, latency, or costs. The free local examples teach the pattern without API use.
