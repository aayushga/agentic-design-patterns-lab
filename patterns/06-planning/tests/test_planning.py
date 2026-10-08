"""Offline planning tests: constraints, dependencies, execution, and adaptation."""
from copy import deepcopy
import importlib

import pytest

app = importlib.import_module("patterns.06-planning.app")
REQUEST = app.PlanningRequest("Prepare an offsite proposal", 20, 600)


def test_plan_then_execute_proposal_satisfies_constraints():
    result = app.run_planning(REQUEST.goal)
    assert result.status == "completed" and result.replans == 0
    assert result.proposal["venue"] == "Cedar Room" and result.proposal["total_cost"] == 500
    assert result.proposal["budget_remaining"] == 100 and result.proposal["booked"] is False
    assert result.proposal["source"] == "simulated demo data"
    attempt = result.attempts[0]
    assert [step.action for step in attempt.plan.steps] == ["check_venue", "check_catering", "build_proposal"]
    assert all(step.status == "success" for step in attempt.steps)
    assert attempt.plan.steps[-1].depends_on == ["venue", "catering"]


@pytest.mark.parametrize("attendees,venue,total", [(10, "Garden Studio", 300), (20, "Cedar Room", 500),
                                                (30, "City Loft", 700)])
def test_local_plan_changes_with_constraints(attendees, venue, total):
    result = app.run_planning("offsite", attendees=attendees, budget=1000)
    assert result.proposal["venue"] == venue and result.proposal["total_cost"] == total


def test_venue_failure_replans_with_new_constraint():
    exclusions = []
    def planner(request, venues, meals):
        exclusions.append((venues.copy(), meals.copy()))
        return app.local_planner(request, venues, meals)
    result = app.run_planning("offsite", planner=planner, unavailable_venues=("cedar",))
    assert result.status == "completed" and result.replans == 1
    assert result.proposal["venue"] == "City Loft" and result.proposal["total_cost"] == 600
    assert exclusions == [(set(), set()), ({"cedar"}, set())]
    assert len(result.attempts[0].steps) == 1 and result.attempts[0].steps[0].status == "error"
    assert "unavailable" in result.attempts[0].steps[0].error


def test_catering_failure_replans_and_preserves_partial_results():
    result = app.run_planning("offsite", budget=800, unavailable_catering=("sandwiches",))
    assert result.status == "completed" and result.replans == 1
    assert result.proposal["catering"] == "Buffet lunch" and result.proposal["total_cost"] == 700
    assert [step.status for step in result.attempts[0].steps] == ["success", "error"]


@pytest.mark.parametrize("kwargs", [{"budget": 450}, {"attendees": 40}])
def test_infeasible_constraints_do_not_execute(kwargs):
    result = app.run_planning("offsite", **kwargs)
    assert result.status == "no_feasible_plan" and result.proposal is None
    assert not result.attempts[0].plan.steps and not result.attempts[0].steps


def test_no_remaining_feasible_choice_after_failure():
    result = app.run_planning("offsite", budget=500, unavailable_venues=("cedar",))
    assert result.status == "no_feasible_plan" and result.replans == 1
    assert len(result.attempts) == 2 and result.proposal is None


@pytest.mark.parametrize("limit", [0, 1])
def test_replanning_budget_bounds_attempts(limit):
    result = app.run_planning("offsite", unavailable_venues=("cedar", "loft"), max_replans=limit)
    assert result.status == "replan_limit" and result.replans == limit
    assert len(result.attempts) == limit + 1 and result.proposal is None


def test_two_failures_then_replanning_reports_infeasibility():
    result = app.run_planning("offsite", unavailable_venues=("cedar", "loft"), max_replans=2)
    assert result.status == "no_feasible_plan" and result.replans == 2
    assert len(result.attempts) == 3


def test_catering_first_plan_executes_with_correct_dependency_ids():
    def planner(*args):
        return app.Plan("Check catering first", [
            app.PlanStep("lunch", "check_catering", "sandwiches", []),
            app.PlanStep("room", "check_venue", "cedar", ["lunch"]),
            app.PlanStep("done", "build_proposal", None, ["room", "lunch"]),
        ])
    result = app.run_planning("offsite", planner=planner)
    assert result.status == "completed" and result.proposal["total_cost"] == 500
    assert result.attempts[0].steps[0].action == "check_catering"


@pytest.mark.parametrize("mutation", [
    lambda p: setattr(p, "reason", ""),
    lambda p: setattr(p, "steps", "bad"),
    lambda p: p.steps.pop(),
    lambda p: setattr(p.steps[1], "step_id", "venue"),
    lambda p: setattr(p.steps[0], "step_id", ""),
    lambda p: setattr(p.steps[0], "action", "book_and_pay"),
    lambda p: setattr(p.steps[1], "action", "check_venue"),
    lambda p: setattr(p.steps[0], "depends_on", ["proposal"]),
    lambda p: setattr(p.steps[0], "depends_on", ["venue"]),
    lambda p: setattr(p.steps[1], "depends_on", ["venue", "venue"]),
    lambda p: setattr(p.steps[1], "depends_on", "venue"),
    lambda p: setattr(p.steps[1], "depends_on", [42]),
    lambda p: setattr(p.steps[0], "option", "missing"),
    lambda p: setattr(p.steps[0], "option", "garden"),
    lambda p: setattr(p.steps[1], "option", None),
    lambda p: setattr(p.steps[-1], "depends_on", ["venue"]),
    lambda p: setattr(p.steps[-1], "option", "cedar"),
    lambda p: setattr(p.steps[0], "option", "loft") or setattr(p.steps[1], "option", "buffet"),
    lambda p: p.steps.reverse(),
])
def test_entire_plan_validated_before_any_execution(monkeypatch, mutation):
    plan = deepcopy(app.local_planner(REQUEST, set(), set()))
    mutation(plan)
    monkeypatch.setattr(app, "execute_plan", lambda *_: pytest.fail("must validate first"))
    with pytest.raises(ValueError):
        app.run_planning("offsite", planner=lambda *_: plan)


@pytest.mark.parametrize("plan", [None, app.Plan("No choices", [])])
def test_missing_or_false_infeasible_plan_rejected(plan):
    with pytest.raises(ValueError):
        app.run_planning("offsite", planner=lambda *_: plan)


def test_excluded_option_cannot_be_reselected():
    plan = app.local_planner(REQUEST, set(), set())
    with pytest.raises(ValueError, match="excluded venue"):
        app.run_planning("offsite", unavailable_venues=("cedar",), planner=lambda *_: plan)


@pytest.mark.parametrize("kwargs", [
    {"goal": ""}, {"goal": None}, {"goal": " "}, {"attendees": True}, {"attendees": 0},
    {"attendees": 101}, {"attendees": 2.5}, {"budget": 0}, {"budget": True},
    {"budget": 100001}, {"budget": 500.5}, {"max_replans": -1}, {"max_replans": 3},
    {"max_replans": True}, {"unavailable_venues": ("missing",)}, {"unavailable_catering": "sandwiches"},
])
def test_invalid_input_rejected_before_planning(kwargs):
    arguments = {"goal": "offsite", **kwargs}
    with pytest.raises(ValueError):
        app.run_planning(**arguments, planner=lambda *_: pytest.fail("must validate first"))


def test_planner_failure_is_not_a_success():
    def broken(*args):
        raise RuntimeError("planner unavailable")
    with pytest.raises(RuntimeError, match="planner unavailable"):
        app.run_planning("offsite", planner=broken)
