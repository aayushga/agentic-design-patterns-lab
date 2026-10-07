"""Demonstrate early approval and honest stopping with unresolved issues."""
from pathlib import Path
import sys

if __package__:
    from ..app import ACKNOWLEDGEMENT, NEXT_STEP, run_reflection
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import ACKNOWLEDGEMENT, NEXT_STEP, run_reflection


def main() -> None:
    query = "I need help with a duplicate invoice."
    complete = f'{ACKNOWLEDGEMENT} You reported: "{query}" {NEXT_STEP}'
    ready = run_reflection(query, initial_draft=complete)
    print(f"Complete reply: approved={ready.approved}, revisions={ready.revisions}, stop={ready.stop_reason}")

    limited = run_reflection(query, max_revisions=0)
    print(f"No revision budget: approved={limited.approved}, stop={limited.stop_reason}")
    print("Unresolved issues:", limited.history[-1].critique.issues)

    def unchanged_reply(query, draft, critique):
        return draft

    stalled = run_reflection(query, reviser=unchanged_reply)
    print(f"Unchanged reply: approved={stalled.approved}, stop={stalled.stop_reason}")
    print("Draft needing human review:", stalled.final_draft)


if __name__ == "__main__":
    main()
