"""Minimal runnable example of the Routing pattern."""

from pathlib import Path
import sys

# Allow running example directly without packaging setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import route_input


if __name__ == "__main__":
    requests = [
        "I was charged twice on my card.",
        "I need help fixing a login error.",
        "I'd like pricing for your pro plan.",
        "Tell me a fun fact.",
    ]

    for item in requests:
        result = route_input(item)
        print(f"Input: {item}")
        print(f"-> Route: {result.route}")
        print(f"-> Response: {result.response}")
        print("-" * 60)
