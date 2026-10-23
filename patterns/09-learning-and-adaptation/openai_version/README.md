# Optional OpenAI Learning and Adaptation

This version uses the official OpenAI Python SDK and Responses API to generate
support replies. The local policy chooses `brief` or `guided` using previous
explicit feedback; the model returns a reply in the chosen structure using
[strict structured outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses).

Feedback updates the Python policy only. No training API, model-weight update,
self-modifying code, implicit rating, or outgoing support action is involved.
The [local version](../README.md) demonstrates the complete learning loop for free.

## Setup and interactive run

From the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r patterns/09-learning-and-adaptation/openai_version/requirements.txt
read -s "OPENAI_API_KEY?OpenAI API key: "; echo
export OPENAI_API_KEY
export OPENAI_MODEL=gpt-6-astra
python patterns/09-learning-and-adaptation/openai_version/openai_adaptation.py --context technical
```

The key entry above uses macOS's default zsh. Never commit a real key.
`.env.example` has placeholders only; scripts read exported variables without
automatically loading `.env` files.

The default model is `gpt-6-astra` with low reasoning effort. `OPENAI_MODEL`
overrides it; the Python `model=` argument takes precedence. The selected model
must support Responses, structured outputs, and low reasoning effort and be
available to your account.

Enter a support query, inspect the printed reply/strategy/scores, then enter
`helpful`, `not_helpful`, or `skip`. Enter `quit` to exit. A bad rating can be
corrected without generating another reply or request. `--context billing`
chooses billing instead; context classification is not part of this example.

## Requests and validation

Each reply generation makes **one billable model request**. Feedback, score
updates, selection, and reset run locally and make none. The CLI defaults to at
most five model request attempts; `--max-requests N` accepts one through twenty.
Failed attempts count toward that model budget. Automatic retries are disabled,
each SDK request has a 30-second timeout, and clients close on success/failure.

Each request is independent, using only the query, context, and selected
strategy. It uses `store=False` to disable Response-object storage; the query
still goes to OpenAI, and this is not a guarantee of zero data retention.
The model does not receive or write the policy's mutable scores or feedback log.

Strict JSON describes `strategy`, `acknowledgement`, and `next_steps`. Local
validation rejects a different strategy, the wrong number of steps, empty or
oversized fields, and line breaks within fields. Brief replies contain one next
step; guided replies contain two. Python renders the validated structure into a
paragraph or bullets, so the chosen format is visible.

Missing keys, SDK/API failures, incomplete responses, empty text/refusals,
malformed JSON, and invalid reply structures fail before an episode is recorded.
No feedback can be assigned to a failed generation. Prompts ask the model to
treat queries as data and avoid fabricated account facts, fixes, or refunds;
this does not guarantee factual accuracy or resistance to prompt injection.
User helpfulness feedback also does not establish factual truth.

Policy state is in memory for the current run. There is no SQLite persistence,
automatic learning across restarts, or automatic reply rewrite. See the local
README for the score update, exploration behavior, and reset semantics.

## Python usage

```python
import importlib

local = importlib.import_module("patterns.09-learning-and-adaptation.app")
optional = importlib.import_module(
    "patterns.09-learning-and-adaptation.openai_version.openai_adaptation"
)
policy = local.AdaptivePolicy()
generator = optional.OpenAIResponder(max_requests=2)
# Billable model request:
first = optional.run_openai_adaptation(
    "Upload fails.", "technical", policy, responder=generator
)
# Free local learning update:
policy.feedback(first.episode_id, "not_helpful")
# Billable request with the policy's next selected strategy:
second = optional.run_openai_adaptation(
    "Upload still fails.", "technical", policy, responder=generator
)
```

Reuse a responder to carry its model-attempt budget across replies. Without one,
`run_openai_adaptation` creates a one-request responder for that call, so limits
do not accumulate between calls. Set `model=` on the shared responder, or on the
function when no responder is supplied; passing both is rejected. The policy
has a separate lifetime episode limit for successful, ratable replies.

Offline tests use fake SDK responses and blocked network connections. They need
no real SDK or key and incur no API charges. They validate feedback propagation
and orchestration, not live model quality, account access, or measured learning gains.

Request safeguards: output is capped at 1500 tokens per attempt, response
storage is disabled (`store=False`), SDK retries are disabled, and clients close on
success or failure. SDK timeouts and cooperative application deadlines are not a
hard whole-run deadline. Token/request caps do not cap input charges or dollar spend.
