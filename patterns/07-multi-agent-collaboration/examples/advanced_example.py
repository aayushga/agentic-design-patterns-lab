"""Show two specialists, a failed specialist, and an unsupported query."""
from pathlib import Path
import sys

if __package__:
    from ..app import billing_specialist, run_collaboration
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import billing_specialist, run_collaboration


def show(label, query, **kwargs):
    result = run_collaboration(query, **kwargs)
    print("\nScenario:", label)
    print("Supervisor assigned:", result.assignment.roles)
    for message in result.handoffs:
        print(f"{message.sender} -> {message.recipient}: {message.status}; {message.error or 'findings delivered'}")
    print("Final reply:\n" + (result.final_response or "No final reply produced"))
    print("Status:", result.status)


def main() -> None:
    query = "I was charged twice. The app crashes during upload."
    show("Billing and technical collaboration", query)

    def unavailable(query):
        raise RuntimeError("Simulated specialist outage")

    show("Technical specialist unavailable", query,
         specialists={"billing": billing_specialist, "technical": unavailable})
    show("Ask for clarification", "Hello, I need help.")


if __name__ == "__main__":
    main()
