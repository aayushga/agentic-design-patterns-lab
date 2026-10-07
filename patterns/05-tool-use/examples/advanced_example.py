"""Show dependent tool calls, an error, and budget exhaustion."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_tool_use
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_tool_use


def show(query, **kwargs):
    result = run_tool_use(query, **kwargs)
    print("\nQuery:", query)
    for step in result.tool_history:
        print(f"{step.name} {step.arguments} -> {step.output or step.error}")
    print("Final answer:", result.final_response)
    print("Stop:", result.stop_reason)


def main() -> None:
    show("What is the total for ORD-1001 including shipping?")
    show("Status of ORD-9999")
    show("Total for ORD-1001", max_tool_calls=1)


if __name__ == "__main__":
    main()
