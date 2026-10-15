"""Show feedback changing the next response strategy without any model calls."""
from pathlib import Path
import sys

if __package__:
    from ..app import AdaptivePolicy, respond
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import AdaptivePolicy, respond


def main() -> None:
    policy = AdaptivePolicy()
    for rating in ("not_helpful", "helpful"):
        answer = respond("The app crashes during upload.", "technical", policy)
        print(f"\nEpisode {answer.episode_id}: {answer.selected_strategy}")
        print(answer.response)
        feedback = policy.feedback(answer.episode_id, rating)
        print("Feedback:", rating)
        print("Scores:", feedback.scores_after)
    answer = respond("Upload still fails.", "technical", policy)
    print("\nNext selected strategy:", answer.selected_strategy)
    print("Reason:", answer.selection_reason)
    print(answer.response)


if __name__ == "__main__":
    main()
