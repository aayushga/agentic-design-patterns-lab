"""Demonstrate revised plans, impossible constraints, and a replanning limit."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_planning
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_planning


def show(label, **kwargs):
    result = run_planning("Prepare a team offsite proposal", **kwargs)
    print("\nScenario:", label)
    for number, attempt in enumerate(result.attempts, 1):
        print(f"Plan {number}: {attempt.plan.reason}")
        for step in attempt.steps:
            print(f"  {step.action}: {step.status}; {step.error or step.output}")
    print(f"Status: {result.status}; replans: {result.replans}")
    print("Final proposal:", result.proposal)


def main() -> None:
    show("Preferred venue becomes unavailable", unavailable_venues=("cedar",))
    show("Budget cannot fit any option", budget=450)
    show("No replanning allowed", unavailable_venues=("cedar",), max_replans=0)


if __name__ == "__main__":
    main()
