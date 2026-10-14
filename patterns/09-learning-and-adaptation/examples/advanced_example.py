"""Show separate context learning, changing feedback, reset, and duplicate rejection."""
from pathlib import Path
import sys

if __package__:
    from ..app import AdaptivePolicy, respond
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import AdaptivePolicy, respond


def rate(policy, context, rating):
    answer = respond("I need help with this issue.", context, policy)
    feedback = policy.feedback(answer.episode_id, rating)
    print(f"{context}: {answer.selected_strategy} -> {rating}; scores={feedback.scores_after}")
    return answer


def main() -> None:
    policy = AdaptivePolicy()
    print("Separate context learning:")
    rate(policy, "technical", "not_helpful")
    rate(policy, "technical", "helpful")
    rate(policy, "billing", "helpful")
    previous = rate(policy, "billing", "not_helpful")
    print("Preferred technical strategy:", policy.select("technical")[0])
    print("Preferred billing strategy:", policy.select("billing")[0])
    print("\nNew negative feedback changes the technical choice:")
    rate(policy, "technical", "not_helpful")
    rate(policy, "technical", "not_helpful")
    print("Technical strategy after new feedback:", policy.select("technical")[0])
    try:
        policy.feedback(previous.episode_id, "helpful")
    except ValueError as exc:
        print("\nDuplicate feedback rejected:", exc)
    policy.reset("technical")
    print("Reset technical scores:", policy.scores("technical"))
    print("Billing scores retained:", policy.scores("billing"))


if __name__ == "__main__":
    main()
