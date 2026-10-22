"""Checkable arithmetic decomposition and bounded search over alternative expressions."""
from __future__ import annotations

import ast
from collections import Counter
from dataclasses import asdict, dataclass
from fractions import Fraction
from itertools import combinations
import json

MAX_EXPRESSION_CHARS = 120
MAX_AST_NODES = 32


@dataclass(frozen=True)
class Puzzle:
    numbers: tuple[int, ...] = (3, 3, 8, 8)
    target: int = 24

    def __post_init__(self):
        if (not isinstance(self.numbers, (tuple, list)) or len(self.numbers) != 4
                or any(type(n) is not int or not 1 <= n <= 12 for n in self.numbers)):
            raise ValueError("Provide exactly four integers from 1 to 12")
        if type(self.target) is not int or not 1 <= self.target <= 100:
            raise ValueError("target must be an integer from 1 to 100")
        object.__setattr__(self, "numbers", tuple(self.numbers))


@dataclass(frozen=True)
class Calculation:
    left: str
    operator: str
    right: str
    result: str


@dataclass(frozen=True)
class Check:
    expression: str
    valid: bool
    value: str | None
    error: str | None
    steps: tuple[Calculation, ...]


@dataclass(frozen=True)
class ReasoningResult:
    puzzle: Puzzle
    method: str
    status: str
    solution: str | None
    checks: tuple[Check, ...]
    explored_states: int
    model_attempts: int
    stop_reason: str


class ExpressionError(ValueError):
    pass


def verify_expression(puzzle: Puzzle, expression: str) -> Check:
    """Interpret only integer literals and binary + - * /; never execute Python."""
    if not isinstance(puzzle, Puzzle):
        raise ValueError("puzzle must be a Puzzle")
    if not isinstance(expression, str) or not 1 <= len(expression) <= MAX_EXPRESSION_CHARS:
        return Check("", False, None, "expression_size_or_type", ())
    text = expression.strip()
    steps: list[Calculation] = []
    used: list[int] = []

    def evaluate(node: ast.AST) -> Fraction:
        if isinstance(node, ast.Constant) and type(node.value) is int and 1 <= node.value <= 12:
            used.append(node.value)
            return Fraction(node.value)
        if not isinstance(node, ast.BinOp) or type(node.op) not in (ast.Add, ast.Sub, ast.Mult, ast.Div):
            raise ExpressionError("disallowed_syntax")
        left, right = evaluate(node.left), evaluate(node.right)
        if isinstance(node.op, ast.Add):
            value, operator = left + right, "+"
        elif isinstance(node.op, ast.Sub):
            value, operator = left - right, "-"
        elif isinstance(node.op, ast.Mult):
            value, operator = left * right, "*"
        else:
            if right == 0:
                raise ExpressionError("division_by_zero")
            value, operator = left / right, "/"
        steps.append(Calculation(str(left), operator, str(right), str(value)))
        return value

    try:
        tree = ast.parse(text, mode="eval")
        if sum(1 for _ in ast.walk(tree)) > MAX_AST_NODES:
            raise ExpressionError("expression_too_complex")
        value = evaluate(tree.body)
        if Counter(used) != Counter(puzzle.numbers):
            raise ExpressionError("numbers_mismatch")
        if value != puzzle.target:
            return Check(text, False, str(value), "wrong_target", tuple(steps))
        return Check(text, True, str(value), None, tuple(steps))
    except (SyntaxError, ValueError, RecursionError) as exc:
        code = str(exc) if isinstance(exc, ExpressionError) else "invalid_syntax"
        return Check(text, False, None, code, tuple(steps))


@dataclass(frozen=True)
class Term:
    value: Fraction
    expression: str


def combine(left: Term, right: Term) -> tuple[Term, ...]:
    """Both orders matter for subtraction and division; omit zero divisors."""
    a, b = left.value, right.value
    options = [(a + b, "+", left, right), (a * b, "*", left, right),
               (a - b, "-", left, right), (b - a, "-", right, left)]
    if b:
        options.append((a / b, "/", left, right))
    if a:
        options.append((b / a, "/", right, left))
    # One representative per pair result is enough: future arithmetic depends
    # on values, and every representative still uses the same two source terms.
    unique: dict[Fraction, Term] = {}
    for value, operator, first, second in options:
        unique.setdefault(value, Term(value, f"({first.expression}{operator}{second.expression})"))
    return tuple(unique.values())


def solve_puzzle(puzzle: Puzzle = Puzzle(), *, max_states: int = 10000) -> ReasoningResult:
    """Depth-first symbolic search, inspired by exploring/backtracking over alternatives."""
    if not isinstance(puzzle, Puzzle):
        raise ValueError("puzzle must be a Puzzle")
    if type(max_states) is not int or not 1 <= max_states <= 100000:
        raise ValueError("max_states must be an integer from 1 to 100000")
    seen: set[tuple[Fraction, ...]] = set()
    exhausted = False

    def visit(terms: tuple[Term, ...]) -> str | None:
        nonlocal exhausted
        key = tuple(sorted(term.value for term in terms))
        if key in seen:
            return None
        if len(seen) >= max_states:
            exhausted = True
            return None
        seen.add(key)
        if len(terms) == 1:
            return terms[0].expression if terms[0].value == puzzle.target else None
        for i, j in combinations(range(len(terms)), 2):
            rest = tuple(term for k, term in enumerate(terms) if k not in (i, j))
            for merged in combine(terms[i], terms[j]):
                solution = visit(rest + (merged,))
                if solution is not None:
                    return solution
                if exhausted:
                    return None
        return None

    solution = visit(tuple(Term(Fraction(n), str(n)) for n in puzzle.numbers))
    if solution is not None:
        check = verify_expression(puzzle, solution)
        if not check.valid:
            raise RuntimeError("Search produced an expression that failed independent verification")
        return ReasoningResult(puzzle, "bounded_search", "solved", solution, (check,), len(seen), 0, "verified_candidate")
    return ReasoningResult(puzzle, "bounded_search", "budget_exhausted" if exhausted else "no_solution",
                           None, (), len(seen), 0, "state_budget" if exhausted else "search_exhausted")


def demo() -> None:
    print("Free local search; all displayed calculations are recomputed with exact fractions.")
    print(json.dumps(asdict(solve_puzzle()), indent=2))


if __name__ == "__main__":
    demo()
