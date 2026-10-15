# Pattern 09: Learning and Adaptation

An agent can change future behavior from feedback about previous outcomes. This
original exercise follows Chapter 9 of Antonio Gulli's *Agentic Design Patterns*
with a small, inspectable online-learning policy for support replies:

**Choose strategy → generate reply → receive explicit feedback → update score → choose again**

There are two strategies: `brief` produces one next step in a paragraph; `guided`
produces two next steps as bullets. Billing and technical contexts have separate
scores. Context is supplied by the caller; this example does not classify tickets.

This is application-level adaptation. It does not update model weights, fine-tune
an LLM, implement PPO/DPO, evolve source code, or reproduce SICA/OpenEvolve. The
policy adapts a choice between existing strategies, not the strategies themselves.

## Difference from Memory and Reflection

Memory retains supplied information for later use. Here, outcomes change a
**selection rule**: a strategy that receives better feedback can become the preferred choice
within this deterministic policy. Reflection critiques and revises
one draft; this example uses feedback on one reply to select a strategy for a
future reply. It does not automatically rewrite the rated reply.

The book discusses many learning mechanisms. This demo covers a simple
feedback-driven, contextual choice with recency-weighted scores, not a general
reinforcement-learning system or a guarantee of continuous improvement.

## Free local run

Use Python 3.10 or newer. From the repository root:

```bash
python patterns/09-learning-and-adaptation/app.py
python patterns/09-learning-and-adaptation/examples/basic_example.py
python patterns/09-learning-and-adaptation/examples/advanced_example.py
```

No SDK, key, network, or API charges are needed. Local replies use fixed templates.
Feedback in the examples is **scripted demonstration data**, not measured user
satisfaction or evidence that one style is generally better.

## Basic output

```text
Episode 1: brief
Thanks for reporting the technical issue. Please share the error message and app version.
Feedback: not_helpful
Scores: {'brief': 0.25, 'guided': 0.5}

Episode 2: guided
Thanks for reporting the technical issue.
- Note the exact error message and your app version.
- Share those details and what you were doing when the issue occurred.
Feedback: helpful
Scores: {'brief': 0.25, 'guided': 0.75}

Next selected strategy: guided
Reason: Choose the highest feedback score (ties prefer brief)
```

The next reply keeps the guided format because its score is higher after both
strategies have received feedback. Reply generation alone never changes scores.

## Learning rule

Both scores start at `0.5`. `helpful` maps to reward `1`; `not_helpful` maps to `0`.
For the strategy used in the rated episode:

```text
new_score = old_score + learning_rate × (reward - old_score)
```

The default learning rate is `0.5`. Thus a negative rating changes `0.5` to `0.25`,
and a positive rating changes `0.5` to `0.75`. A valid learning rate is greater
than zero and at most one. Newer feedback has more influence than older feedback;
updates occur in feedback-arrival order, not episode-creation order.

Strategies with no received feedback are tried first, in `brief`, then `guided`
order. Once both have feedback, selection takes the higher score; ties prefer
brief. Skipping feedback does not mark a strategy as evaluated, so it can be
selected again. This is limited initial exploration, not continual exploration,
a posterior probability, or a confidence estimate. Noisy or biased feedback can
produce poor choices; the demo does not prove factual correctness or optimality.

## Advanced output

The advanced example learns opposite choices for different contexts:

```text
Preferred technical strategy: guided
Preferred billing strategy: brief
```

Two later negative ratings for guided technical replies lower its score:

```text
technical: guided -> not_helpful; scores={'brief': 0.25, 'guided': 0.375}
technical: guided -> not_helpful; scores={'brief': 0.25, 'guided': 0.1875}
Technical strategy after new feedback: brief
```

It also rejects a second rating for the same episode, then resets technical
learning to neutral scores while retaining billing's scores. Reset invalidates
that context's previous feedback IDs and does not recycle IDs or the episode
budget.

## Python API and result

Import with
`importlib.import_module("patterns.09-learning-and-adaptation.app")` from the
repository root, then:

```python
policy = module.AdaptivePolicy(learning_rate=0.5, max_episodes=20)
answer = module.respond("Upload fails.", "technical", policy)
feedback = policy.feedback(answer.episode_id, "not_helpful")
next_answer = module.respond("Upload still fails.", "technical", policy)
```

`AdaptationResult` includes the episode ID, query, context, selected strategy,
selection reason, scores before generation, structured reply, and rendered
response. `FeedbackResult` records the rated context/strategy, rating, scores
before/after, and the next preferred strategy. Convert either using
`dataclasses.asdict` to inspect its JSON-ready data.

Unknown IDs, invalid ratings, and duplicate feedback fail without updating scores.
Ratings are attributed to the episode's original context and strategy. Only
usable replies matching the selected strategy are recorded: brief needs one step,
guided needs two, with bounded non-empty acknowledgement/step fields. Failures
leave no new episode to rate. Query length is limited to 1000 characters.

One `AdaptivePolicy` instance is one learner. Do not share it across unrelated
users unless pooled feedback is intentional. Scores and episode metadata live
in memory and disappear on restart. Internal episode metadata stores context,
strategy, and rating status, not the query/reply. The default lifetime limit is
20 issued episodes, configurable from one through 100; generation stops before
a responder call when it is reached. This is a single-threaded demo with trusted
caller-supplied feedback, not a persistence or authentication service.

## Optional OpenAI version and offline tests

[OpenAI setup](openai_version/README.md) uses the official SDK and `gpt-6-astra`
by default. The same policy selects the strategy; OpenAI generates a structured
reply under that constraint. Feedback, selection, and reset make no API calls.

```bash
python -m pip install -r patterns/09-learning-and-adaptation/requirements.txt
python -m pytest patterns/09-learning-and-adaptation/tests -q
```

Tests verify actual strategy changes, response structure, attribution, separate
contexts, changing feedback, duplicate protection, reset, bounds, failed episodes,
and SDK requests. Fake SDK responses and blocked network connections keep them
free of live API calls, real keys, and SDK-installation requirements.
