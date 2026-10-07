"""Show one tool call, its observation, and an answer based on that observation."""
from pathlib import Path
import sys

if __package__:
    from ..app import run_tool_use
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import run_tool_use


def main() -> None:
    query = "What is the status of ORD-1001?"
    result = run_tool_use(query)
    print("Query:", query)
    for step in result.tool_history:
        print(f"Tool call: {step.name}({step.arguments})")
        print("Tool result:", step.output)
    print("Final answer:", result.final_response)
    print("Stop:", result.stop_reason)


if __name__ == "__main__":
    main()
