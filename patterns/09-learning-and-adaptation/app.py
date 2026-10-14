"""Learning and Adaptation: explicit feedback changes a small reply-selection policy.

This is an online feedback heuristic, not model training or source-code evolution.
One policy instance is one learner; its state is in memory and resets on restart.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict, dataclass
import json
from typing import Callable

CONTEXTS = ("billing", "technical")
STRATEGIES = ("brief", "guided")
RATINGS = {"helpful": 1.0, "not_helpful": 0.0}
NEXT_STEPS = {
    "billing": {
        "brief": ["Please share your invoice number so billing can investigate."],
        "guided": ["Find the invoice number for the charge you reported.",
                   "Share that number and the charge date so billing can investigate."],
    },
    "technical": {
        "brief": ["Please share the error message and app version."],
        "guided": ["Note the exact error message and your app version.",
                   "Share those details and what you were doing when the issue occurred."],
    },
}


@dataclass
class StrategyStats:
    score: float = 0.5
    feedback_count: int = 0


@dataclass
class Reply:
    strategy: str
    acknowledgement: str
    next_steps: list[str]


@dataclass
class AdaptationResult:
    episode_id: int
    original_query: str
    context: str
    selected_strategy: str
    selection_reason: str
    scores_before: dict[str, float]
    reply: Reply
    response: str


@dataclass
class FeedbackResult:
    episode_id: int
    context: str
    strategy: str
    rating: str
    scores_before: dict[str, float]
    scores_after: dict[str, float]
    next_strategy: str


class AdaptivePolicy:
    """Explore unrated strategies first, then choose the highest smoothed score.

    Feedback updates score += learning_rate * (reward - score). Counts track
    received ratings, not responses issued. Scores are not confidence estimates.
    """
    def __init__(self, *, learning_rate: float = 0.5, max_episodes: int = 20):
        if type(learning_rate) not in (int, float) or not 0 < learning_rate <= 1:
            raise ValueError("learning_rate must be a number greater than 0 and at most 1")
        if type(max_episodes) is not int or not 1 <= max_episodes <= 100:
            raise ValueError("max_episodes must be an integer between 1 and 100")
        self.learning_rate = learning_rate
        self.max_episodes = max_episodes
        self._stats = {context: {strategy: StrategyStats() for strategy in STRATEGIES} for context in CONTEXTS}
        self._episodes = {}
        self._next_id = 1

    def statistics(self, context: str) -> dict[str, StrategyStats]:
        validate_context(context)
        return deepcopy(self._stats[context])

    def scores(self, context: str) -> dict[str, float]:
        return {name: stats.score for name, stats in self.statistics(context).items()}

    def select(self, context: str) -> tuple[str, str]:
        validate_context(context)
        for strategy in STRATEGIES:
            if self._stats[context][strategy].feedback_count == 0:
                return strategy, "Try a strategy with no feedback yet"
        strategy = max(STRATEGIES, key=lambda name: self._stats[context][name].score)
        return strategy, "Choose the highest feedback score (ties prefer brief)"

    def ensure_capacity(self) -> None:
        if self._next_id > self.max_episodes:
            raise ValueError("Episode limit reached; create a new learner for another run")

    def record(self, context: str, strategy: str) -> int:
        validate_context(context)
        if not isinstance(strategy, str) or strategy not in STRATEGIES:
            raise ValueError("Unknown strategy")
        self.ensure_capacity()
        episode_id = self._next_id
        self._next_id += 1
        self._episodes[episode_id] = {"context": context, "strategy": strategy, "rated": False}
        return episode_id

    def feedback(self, episode_id: int, rating: str) -> FeedbackResult:
        if type(episode_id) is not int or episode_id not in self._episodes:
            raise ValueError("Unknown or reset episode ID")
        if not isinstance(rating, str) or rating not in RATINGS:
            raise ValueError("Rating must be helpful or not_helpful")
        episode = self._episodes[episode_id]
        if episode["rated"]:
            raise ValueError("Feedback already recorded for this episode")
        context, strategy = episode["context"], episode["strategy"]
        before = self.scores(context)
        stats = self._stats[context][strategy]
        stats.score += self.learning_rate * (RATINGS[rating] - stats.score)
        stats.feedback_count += 1
        episode["rated"] = True
        return FeedbackResult(episode_id, context, strategy, rating, before,
                              self.scores(context), self.select(context)[0])

    def reset(self, context: str) -> None:
        """Clear one context's learning and invalidate its prior episode IDs."""
        validate_context(context)
        self._stats[context] = {strategy: StrategyStats() for strategy in STRATEGIES}
        self._episodes = {identifier: episode for identifier, episode in self._episodes.items()
                          if episode["context"] != context}
        # IDs and the lifetime episode limit are not recycled by reset.


def validate_context(context: str) -> None:
    if not isinstance(context, str) or context not in CONTEXTS:
        raise ValueError("Context must be billing or technical")


def local_responder(query: str, context: str, strategy: str) -> Reply:
    return Reply(strategy, f"Thanks for reporting the {context} issue.", list(NEXT_STEPS[context][strategy]))


Responder = Callable[[str, str, str], Reply]


def validate_reply(reply: Reply, strategy: str) -> None:
    expected_steps = 1 if strategy == "brief" else 2
    if (not isinstance(reply, Reply) or reply.strategy != strategy
            or not isinstance(reply.acknowledgement, str) or not reply.acknowledgement.strip()
            or len(reply.acknowledgement) > 200 or "\n" in reply.acknowledgement or "\r" in reply.acknowledgement
            or not isinstance(reply.next_steps, list) or len(reply.next_steps) != expected_steps
            or not all(isinstance(step, str) and step.strip() and len(step) <= 300
                       and "\n" not in step and "\r" not in step for step in reply.next_steps)):
        raise ValueError("Reply must match the selected strategy and contain bounded acknowledgement/steps")


def respond(query: str, context: str, policy: AdaptivePolicy, *,
            responder: Responder = local_responder) -> AdaptationResult:
    """Generate a valid response before recording an episode eligible for feedback."""
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ValueError("Query must contain text and be at most 1000 characters")
    validate_context(context)
    policy.ensure_capacity()
    strategy, reason = policy.select(context)
    before = policy.scores(context)
    reply = responder(query.strip(), context, strategy)
    validate_reply(reply, strategy)
    reply = deepcopy(reply)
    reply.acknowledgement = reply.acknowledgement.strip()
    reply.next_steps = [step.strip() for step in reply.next_steps]
    response = (reply.acknowledgement + " " + reply.next_steps[0] if strategy == "brief"
                else reply.acknowledgement + "\n" + "\n".join(f"- {step}" for step in reply.next_steps))
    identifier = policy.record(context, strategy)
    return AdaptationResult(identifier, query, context, strategy, reason, before, reply, response)


def main() -> None:
    policy = AdaptivePolicy()
    results = []
    for rating in ("not_helpful", "helpful"):
        answer = respond("Upload fails.", "technical", policy)
        results.append({"answer": asdict(answer), "feedback": asdict(policy.feedback(answer.episode_id, rating))})
    results.append({"next_answer": asdict(respond("Upload still fails.", "technical", policy))})
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
