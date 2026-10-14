"""Show one specialist's findings being passed to a separate writer."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_collaboration
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_collaboration


def main() -> None:
    result = run_collaboration("I was charged twice for my subscription.")
    print("Query:", result.original_query)
    print("Supervisor assigned:", ", ".join(result.assignment.roles))
    for message in result.handoffs:
        print(f"Handoff: {message.sender} -> {message.recipient}; {message.status}")
        for finding in message.findings:
            print("Evidence:", finding.evidence)
            print("Assessment:", finding.assessment)
            print("Next step:", finding.next_step)
    print("Final reply:\n" + result.final_response)
    print("Status:", result.status)


if __name__ == "__main__":
    main()
