"""Budget, time, quality, and availability change the chosen response path."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import BackendUnavailable, Budget, ResourceAwareAgent, WorkItem, local_backend


def show(label, result):
    print(f"\n{label}: {result.status}; profile={result.selected_profile}; "
          f"calls={result.calls_made}; reserved={result.reserved_output_tokens}; "
          f"remaining={result.remaining_output_tokens}")
    for step in result.trace:
        print("  " + step)
    if result.answer:
        print("  Answer:", result.answer)


if __name__ == "__main__":
    print("Free local simulation; no model calls or waiting.")
    item = WorkItem("Compare recovery options for a login problem.", "detailed")
    show("Enough resources", ResourceAwareAgent().answer(item))
    show("Small token allowance", ResourceAwareAgent(Budget(output_tokens=600)).answer(item))
    show("Detailed response required", ResourceAwareAgent(Budget(output_tokens=600)).answer(item, allow_degraded=False))
    show("Short time forecast", ResourceAwareAgent(Budget(seconds=2)).answer(item))

    def unavailable_thorough(item, profile, timeout):
        if profile.name == "thorough":
            raise BackendUnavailable()
        return local_backend(item, profile, timeout)

    show("Preferred backend unavailable", ResourceAwareAgent(backend=unavailable_thorough).answer(item))
    agent = ResourceAwareAgent(Budget(output_tokens=600, max_calls=1))
    show("Use remaining allowance", agent.answer(WorkItem("Report a login problem.")))
    show("Different request after allowance spent", agent.answer(WorkItem("Report a billing problem.")))
