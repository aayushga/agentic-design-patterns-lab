"""Planning: propose a constrained offsite plan, execute it, and adapt to failures.

All prices and availability are fictional. Execution produces a proposal only;
no booking, payment, network request, or generated code is performed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from typing import Callable

VENUES = {
    "cedar": {"name": "Cedar Room", "capacity": 25, "cost": 300},
    "loft": {"name": "City Loft", "capacity": 30, "cost": 400},
    "garden": {"name": "Garden Studio", "capacity": 15, "cost": 200},
}
CATERING = {
    "sandwiches": {"name": "Sandwich lunch", "cost_per_person": 10},
    "buffet": {"name": "Buffet lunch", "cost_per_person": 20},
}


@dataclass
class PlanningRequest:
    goal: str
    attendees: int
    budget: int


@dataclass
class PlanStep:
    step_id: str
    action: str
    option: str | None
    depends_on: list[str]


@dataclass
class Plan:
    reason: str
    steps: list[PlanStep]


@dataclass
class StepResult:
    step_id: str
    action: str
    status: str
    output: dict | None = None
    error: str | None = None


@dataclass
class PlanningAttempt:
    plan: Plan
    status: str
    steps: list[StepResult]


@dataclass
class PlanningResult:
    request: PlanningRequest
    status: str
    replans: int
    proposal: dict | None
    attempts: list[PlanningAttempt]


Planner = Callable[[PlanningRequest, set[str], set[str]], Plan]


def feasible_choices(request: PlanningRequest, excluded_venues: set[str],
                     excluded_catering: set[str]) -> list[tuple[int, str, str]]:
    """Enumerate catalog combinations that satisfy capacity and budget."""
    return sorted(
        (venue["cost"] + meal["cost_per_person"] * request.attendees, venue_id, meal_id)
        for venue_id, venue in VENUES.items()
        for meal_id, meal in CATERING.items()
        if venue_id not in excluded_venues and meal_id not in excluded_catering
        and venue["capacity"] >= request.attendees
        and venue["cost"] + meal["cost_per_person"] * request.attendees <= request.budget
    )


def local_planner(request: PlanningRequest, excluded_venues: set[str],
                  excluded_catering: set[str]) -> Plan:
    """Select the cheapest feasible combination in this small fictional catalog."""
    choices = feasible_choices(request, excluded_venues, excluded_catering)
    if not choices:
        return Plan("No catalog combination fits the capacity, budget, and known availability.", [])
    total, venue_id, meal_id = choices[0]
    return Plan(f"Lowest-cost feasible catalog combination: {total} USD.", [
        PlanStep("venue", "check_venue", venue_id, []),
        PlanStep("catering", "check_catering", meal_id, []),
        PlanStep("proposal", "build_proposal", None, ["venue", "catering"]),
    ])


def validate_request(goal: str, attendees: int, budget: int, max_replans: int) -> None:
    if not isinstance(goal, str) or not goal.strip():
        raise ValueError("Please provide a non-empty goal")
    if type(attendees) is not int or not 1 <= attendees <= 100:
        raise ValueError("attendees must be an integer between 1 and 100")
    if type(budget) is not int or not 1 <= budget <= 100000:
        raise ValueError("budget must be a whole USD integer between 1 and 100000")
    if type(max_replans) is not int or not 0 <= max_replans <= 2:
        raise ValueError("max_replans must be an integer between 0 and 2")


def validate_plan(plan: Plan, request: PlanningRequest, excluded_venues: set[str],
                  excluded_catering: set[str]) -> None:
    """Validate the complete plan before executing even its first step."""
    if (not isinstance(plan, Plan) or not isinstance(plan.reason, str) or not plan.reason.strip()
            or not isinstance(plan.steps, list)):
        raise ValueError("Planner must return a Plan with a reason and step list")
    if not plan.steps:
        if feasible_choices(request, excluded_venues, excluded_catering):
            raise ValueError("Planner claimed no feasible plan despite available catalog choices")
        return
    if len(plan.steps) != 3:
        raise ValueError("Plan must contain exactly three steps")
    seen = set()
    actions = {}
    for step in plan.steps:
        if (not isinstance(step, PlanStep) or not isinstance(step.step_id, str)
                or not step.step_id.strip() or step.step_id in seen):
            raise ValueError("Plan steps require unique non-empty IDs")
        if not isinstance(step.action, str) or step.action not in {"check_venue", "check_catering", "build_proposal"}:
            raise ValueError("Unknown plan action")
        if step.action in actions:
            raise ValueError("Each plan action must appear exactly once")
        if (not isinstance(step.depends_on, list)
                or not all(isinstance(item, str) for item in step.depends_on)
                or len(set(step.depends_on)) != len(step.depends_on)
                or not set(step.depends_on) <= seen):
            raise ValueError("Dependencies must be unique earlier step IDs")
        if step.action == "check_venue":
            if not isinstance(step.option, str) or step.option not in VENUES or step.option in excluded_venues:
                raise ValueError("Plan selected an unknown or excluded venue")
            if VENUES[step.option]["capacity"] < request.attendees:
                raise ValueError("Venue capacity is insufficient")
        elif step.action == "check_catering":
            if not isinstance(step.option, str) or step.option not in CATERING or step.option in excluded_catering:
                raise ValueError("Plan selected unknown or excluded catering")
        else:
            required = {item.step_id for item in actions.values()}
            if (set(actions) != {"check_venue", "check_catering"}
                    or set(step.depends_on) != required or step.option is not None):
                raise ValueError("Proposal must depend on both checks and have no option")
        seen.add(step.step_id)
        actions[step.action] = step
    venue = VENUES[actions["check_venue"].option]
    meal = CATERING[actions["check_catering"].option]
    if venue["cost"] + meal["cost_per_person"] * request.attendees > request.budget:
        raise ValueError("Plan exceeds the budget")


def execute_plan(plan: Plan, request: PlanningRequest, unavailable_venues: set[str],
                 unavailable_catering: set[str]) -> PlanningAttempt:
    """Execute a validated plan against simulated availability, stopping on failure."""
    results = []
    outputs = {}
    for step in plan.steps:
        if step.action == "check_venue":
            if step.option in unavailable_venues:
                results.append(StepResult(step.step_id, step.action, "error",
                                          error=f"Venue {step.option} is unavailable in this simulation"))
                return PlanningAttempt(plan, "failed", results)
            outputs[step.action] = {"venue_id": step.option, **VENUES[step.option]}
        elif step.action == "check_catering":
            if step.option in unavailable_catering:
                results.append(StepResult(step.step_id, step.action, "error",
                                          error=f"Catering {step.option} is unavailable in this simulation"))
                return PlanningAttempt(plan, "failed", results)
            meal = CATERING[step.option]
            outputs[step.action] = {"catering_id": step.option, **meal,
                                    "cost": meal["cost_per_person"] * request.attendees}
        else:
            venue, meal = outputs["check_venue"], outputs["check_catering"]
            total = venue["cost"] + meal["cost"]
            outputs[step.action] = {
                "goal": request.goal, "attendees": request.attendees,
                "venue": venue["name"], "catering": meal["name"],
                "total_cost": total, "budget_remaining": request.budget - total,
                "currency": "USD", "source": "simulated demo data", "booked": False,
            }
        results.append(StepResult(step.step_id, step.action, "success", output=outputs[step.action]))
    return PlanningAttempt(plan, "completed", results)


def run_planning(goal: str, *, attendees: int = 20, budget: int = 600,
                 max_replans: int = 1, planner: Planner = local_planner,
                 unavailable_venues: tuple[str, ...] = (),
                 unavailable_catering: tuple[str, ...] = ()) -> PlanningResult:
    """Plan first; validate; execute; replan after newly discovered unavailability.

    Failed attempts retain their observations. Replanning starts afresh because
    these checks have no side effects. Invalid plans and planner failures propagate.
    """
    validate_request(goal, attendees, budget, max_replans)
    for supplied, catalog in [(unavailable_venues, VENUES), (unavailable_catering, CATERING)]:
        if (not isinstance(supplied, (tuple, list, set))
                or not all(isinstance(item, str) and item in catalog for item in supplied)):
            raise ValueError("Unavailable options must be known catalog IDs")
    request = PlanningRequest(goal, attendees, budget)
    excluded_venues, excluded_catering = set(), set()
    attempts = []
    replans = 0
    while True:
        plan = planner(request, set(excluded_venues), set(excluded_catering))
        validate_plan(plan, request, excluded_venues, excluded_catering)
        if not plan.steps:
            attempts.append(PlanningAttempt(plan, "no_feasible_plan", []))
            return PlanningResult(request, "no_feasible_plan", replans, None, attempts)
        attempt = execute_plan(plan, request, set(unavailable_venues), set(unavailable_catering))
        attempts.append(attempt)
        if attempt.status == "completed":
            return PlanningResult(request, "completed", replans, attempt.steps[-1].output, attempts)
        if replans >= max_replans:
            return PlanningResult(request, "replan_limit", replans, None, attempts)
        failed = attempt.steps[-1]
        selected = next(step for step in plan.steps if step.step_id == failed.step_id)
        if failed.action == "check_venue":
            excluded_venues.add(selected.option)
        else:
            excluded_catering.add(selected.option)
        replans += 1


def main() -> None:
    print(json.dumps(asdict(run_planning("Prepare a team offsite proposal")), indent=2))


if __name__ == "__main__":
    main()
