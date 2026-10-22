"""Verify a proposed expression and show its checkable calculation steps."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Puzzle, verify_expression

if __name__ == "__main__":
    puzzle = Puzzle((2, 3, 4, 6))
    print("Use 2, 3, 4, 6 exactly once to make 24.")
    check = verify_expression(puzzle, "((6+4)-2)*3")
    print(json.dumps(asdict(check), indent=2))
