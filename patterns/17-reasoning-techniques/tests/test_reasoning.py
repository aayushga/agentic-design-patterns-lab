"""Exact arithmetic, allowed syntax, and honest bounded-search outcomes."""
import importlib
from fractions import Fraction
from itertools import permutations

import pytest

app = importlib.import_module("patterns.17-reasoning-techniques.app")


def test_decomposition_is_a_checkable_calculation():
    check = app.verify_expression(app.Puzzle((2, 3, 4, 6)), "((6+4)-2)*3")
    assert check.valid and check.value == "24" and check.error is None
    assert [(s.left, s.operator, s.right, s.result) for s in check.steps] == [
        ("6", "+", "4", "10"), ("10", "-", "2", "8"), ("8", "*", "3", "24")]


def test_fractional_intermediates_are_exact_not_float_comparisons():
    check = app.verify_expression(app.Puzzle(), "8/(3-8/3)")
    assert check.valid and check.value == "24"
    assert [s.result for s in check.steps] == ["8/3", "1/3", "24"]


def test_wrong_target_keeps_observed_value_for_correction():
    check = app.verify_expression(app.Puzzle(), "(8-3)*(8-3)")
    assert not check.valid and check.value == "25" and check.error == "wrong_target"


@pytest.mark.parametrize("expression", ["8*3", "8*3+3-3", "8*3+8-8", "3+3+8+8+3"])
def test_all_four_numbers_and_their_multiplicities_must_match(expression):
    check = app.verify_expression(app.Puzzle(), expression)
    assert not check.valid and check.error == "numbers_mismatch"


def test_zero_division_is_rejected_without_crashing():
    check = app.verify_expression(app.Puzzle(), "8/(3-3)*8")
    assert not check.valid and check.error == "division_by_zero"


@pytest.mark.parametrize("expression", [
    "__import__('os').system('echo forbidden')", "sum([3,3,8,8])", "8**3-8-3", "8//3+8+3",
    "8%3+8+3", "-3+3+8+8", "+3+3+8+8", "3.0+3+8+8", "True+3+8+8",
    "[3,3,8,8]", "(3,3,8,8)", "lambda: 24", "8 if 3 else 8", "x+3+8+8",
])
def test_non_arithmetic_or_disallowed_syntax_cannot_be_a_solution(expression, monkeypatch):
    import os
    monkeypatch.setattr(os, "system", lambda *args: pytest.fail("Expression executed a shell call"))
    check = app.verify_expression(app.Puzzle(), expression)
    assert not check.valid and check.error in ("disallowed_syntax", "expression_too_complex")


@pytest.mark.parametrize("expression", [None, 24, "", " ", "(", "8/(3-8/3)" + " " * 120])
def test_invalid_size_type_or_syntax_is_a_failed_check(expression):
    assert not app.verify_expression(app.Puzzle(), expression).valid


def test_raw_length_boundary_is_checked_before_trimming():
    expression = "8/(3-8/3)"
    assert app.verify_expression(app.Puzzle(), expression.ljust(120)).valid
    assert app.verify_expression(app.Puzzle(), expression.ljust(121)).error == "expression_size_or_type"


def test_ast_complexity_is_bounded():
    check = app.verify_expression(app.Puzzle(), "+".join(["1"] * 20))
    assert check.error == "expression_too_complex"


@pytest.mark.parametrize("numbers", [(3, 3, 8, 8), (2, 3, 4, 6), (1, 5, 5, 5), (1, 2, 3, 4), (12, 12, 1, 1)])
def test_search_finds_independently_verified_solutions(numbers):
    puzzle = app.Puzzle(numbers)
    result = app.solve_puzzle(puzzle)
    assert result.status == "solved" and result.solution
    assert app.verify_expression(puzzle, result.solution).valid
    assert result.checks[0].value == "24"
    assert 1 <= result.explored_states <= 10000 and result.model_attempts == 0


def test_tiny_budget_never_claims_impossibility():
    result = app.solve_puzzle(max_states=1)
    assert result.status == "budget_exhausted" and result.stop_reason == "state_budget"
    assert result.explored_states == 1 and result.solution is None and not result.checks


def test_fully_exhausted_impossible_puzzle_has_distinct_status():
    result = app.solve_puzzle(app.Puzzle((1, 1, 1, 1)))
    assert result.status == "no_solution" and result.stop_reason == "search_exhausted"
    assert result.solution is None and result.explored_states < 10000


def test_non_default_target_and_duplicate_inputs():
    puzzle = app.Puzzle([1, 1, 1, 1], target=4)
    assert puzzle.numbers == (1, 1, 1, 1)
    result = app.solve_puzzle(puzzle)
    assert result.status == "solved" and result.checks[0].value == "4"


def test_all_input_orders_preserve_solvability():
    for numbers in set(permutations((3, 3, 8, 8))):
        assert app.solve_puzzle(app.Puzzle(numbers)).status == "solved"


def test_combine_includes_noncommutative_orders_and_omits_zero_divisors():
    terms = app.combine(app.Term(Fraction(3), "3"), app.Term(Fraction(8), "8"))
    assert {Fraction(-5), Fraction(5), Fraction(3, 8), Fraction(8, 3)} <= {t.value for t in terms}
    with_zero = app.combine(app.Term(Fraction(0), "(3-3)"), app.Term(Fraction(8), "8"))
    assert {t.value for t in with_zero} == {Fraction(0), Fraction(8), Fraction(-8)}


@pytest.mark.parametrize("numbers,target", [((1, 2, 3), 24), ((1, 2, 3, 4, 5), 24),
    ((True, 2, 3, 4), 24), ((0, 2, 3, 4), 24), ((13, 2, 3, 4), 24),
    ((1.0, 2, 3, 4), 24), (None, 24), ((1, 2, 3, 4), True), ((1, 2, 3, 4), 101)])
def test_invalid_puzzles_are_rejected(numbers, target):
    with pytest.raises(ValueError):
        app.Puzzle(numbers, target)


@pytest.mark.parametrize("budget", [0, -1, True, 1.5, 100001])
def test_invalid_state_budgets_are_rejected(budget):
    with pytest.raises(ValueError):
        app.solve_puzzle(max_states=budget)
