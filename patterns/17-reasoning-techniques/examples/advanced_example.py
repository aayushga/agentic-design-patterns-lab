"""Compare a wrong proposal, branching search, exhausted budget, and impossibility."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Puzzle, solve_puzzle, verify_expression

if __name__ == "__main__":
    puzzle = Puzzle((3, 3, 8, 8))
    wrong = verify_expression(puzzle, "(8-3)*(8-3)")
    print(f"Initial proposal: {wrong.expression} = {wrong.value}; valid={wrong.valid}; error={wrong.error}")
    result = solve_puzzle(puzzle)
    print(f"Alternative search: {result.status}; expression={result.solution}; states={result.explored_states}")
    for step in result.checks[0].steps:
        left = f"({step.left})" if "/" in step.left else step.left
        right = f"({step.right})" if "/" in step.right else step.right
        print(f"  {left} {step.operator} {right} = {step.result}")
    limited = solve_puzzle(puzzle, max_states=1)
    print(f"Tiny search budget: {limited.status}; reason={limited.stop_reason}; states={limited.explored_states}")
    impossible = solve_puzzle(Puzzle((1, 1, 1, 1)))
    print(f"Exhaustive search for 1,1,1,1: {impossible.status}; reason={impossible.stop_reason}; states={impossible.explored_states}")
