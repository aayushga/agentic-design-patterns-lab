"""Show the explicit plan before its execution trace and final proposal."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_planning
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_planning


def main() -> None:
    result = run_planning("Prepare a team offsite proposal", attendees=20, budget=600)
    print("Goal:", result.request.goal)
    print(f"Constraints: {result.request.attendees} attendees; {result.request.budget} USD budget")
    for attempt in result.attempts:
        print("Plan:", attempt.plan.reason)
        for step in attempt.plan.steps:
            print(f"- {step.step_id}: {step.action}({step.option}); depends on {step.depends_on}")
        print("Execution:")
        for step in attempt.steps:
            print(f"- {step.step_id}: {step.status}")
    print("Proposal:", result.proposal)
    print(f"Status: {result.status}; replans: {result.replans}")


if __name__ == "__main__":
    main()
