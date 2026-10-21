"""One economical response, then an exact cache hit without another attempt."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Budget, ResourceAwareAgent, WorkItem

if __name__ == "__main__":
    print("Free local simulation; token reservations are illustrative.")
    agent = ResourceAwareAgent(Budget(output_tokens=600, max_calls=1))
    item = WorkItem("How should I report a login problem?")
    for label in ("First request", "Repeated request"):
        print(label)
        print(json.dumps(asdict(agent.answer(item)), indent=2))
