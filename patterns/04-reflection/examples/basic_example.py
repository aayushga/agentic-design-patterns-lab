"""Show before, feedback, and after for one free local reflection cycle."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_reflection
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_reflection


def main() -> None:
    result = run_reflection("The app crashes when I upload a file.")
    print("Initial draft:", result.initial_draft)
    print("Critic's findings:")
    for issue in result.history[0].critique.issues:
        print(f"- {issue}")
    print("Revised reply:", result.final_draft)
    print(f"Approved: {result.approved}; revisions: {result.revisions}; stop: {result.stop_reason}")


if __name__ == "__main__":
    main()
