"""Measurable ticket-triage goals, observed progress, and bounded adaptation.

Everything is an in-memory simulation. Triage is not customer-issue resolution.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math
import time
from typing import Callable


def bounded_text(value: str, name: str, limit: int) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError(f"{name} must be non-empty text of at most {limit} characters")


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    priority: str = "normal"
    context_ready: bool = True
    context_available: bool = True
    triaged: bool = False

    def __post_init__(self):
        bounded_text(self.ticket_id, "ticket_id", 40)
        if self.priority not in ("high", "normal"):
            raise ValueError("priority must be high or normal")
        if any(type(value) is not bool for value in
               (self.context_ready, self.context_available, self.triaged)):
            raise ValueError("Ticket state flags must be booleans")
        if self.triaged and not self.context_ready:
            raise ValueError("A triaged ticket must have context")


@dataclass(frozen=True)
class Goal:
    required_ticket_ids: tuple[str, ...]
    max_steps: int = 6
    max_stalled_steps: int = 2
    deadline_seconds: float = 30.0

    def __post_init__(self):
        if not isinstance(self.required_ticket_ids, tuple) or not 1 <= len(self.required_ticket_ids) <= 20:
            raise ValueError("required_ticket_ids must be a tuple of 1 to 20 ticket IDs")
        for ticket_id in self.required_ticket_ids:
            bounded_text(ticket_id, "required ticket ID", 40)
        if len(set(self.required_ticket_ids)) != len(self.required_ticket_ids):
            raise ValueError("Goal ticket IDs must be unique")
        for name, value in (("max_steps", self.max_steps), ("max_stalled_steps", self.max_stalled_steps)):
            if type(value) is not int or not 1 <= value <= 20:
                raise ValueError(f"{name} must be an integer between 1 and 20")
        if (type(self.deadline_seconds) not in (int, float)
                or not math.isfinite(self.deadline_seconds) or not 0 < self.deadline_seconds <= 300):
            raise ValueError("deadline_seconds must be finite and between 0 (exclusive) and 300")


@dataclass(frozen=True)
class Action:
    kind: str
    ticket_id: str

    def __post_init__(self):
        if self.kind not in ("collect_context", "triage"):
            raise ValueError("Action must be collect_context or triage")
        bounded_text(self.ticket_id, "ticket_id", 40)


@dataclass(frozen=True)
class Progress:
    triaged: int
    target: int
    completed_fraction: float
    pending_ids: tuple[str, ...]
    high_priority_pending: int
    remaining_work: int


@dataclass(frozen=True)
class Observation:
    status: str
    detail: str


@dataclass(frozen=True)
class Step:
    number: int
    action: Action
    observation: Observation
    progress: Progress
    stalled_steps: int


@dataclass(frozen=True)
class GoalResult:
    status: str
    reason: str
    goal: Goal
    progress: Progress
    history: tuple[Step, ...]
    tickets: tuple[Ticket, ...]
    source: str = "simulated demo data"


def validate_scope(tickets: tuple[Ticket, ...], goal: Goal) -> None:
    if not isinstance(goal, Goal):
        raise ValueError("goal must be a Goal")
    if not isinstance(tickets, tuple) or not 1 <= len(tickets) <= 20 or any(not isinstance(t, Ticket) for t in tickets):
        raise ValueError("tickets must be a tuple of 1 to 20 Ticket objects")
    ids = {ticket.ticket_id for ticket in tickets}
    if len(ids) != len(tickets):
        raise ValueError("Ticket IDs must be unique")
    if not set(goal.required_ticket_ids) <= ids:
        raise ValueError("Every goal ticket must exist in the supplied queue")


def measure(tickets: tuple[Ticket, ...], goal: Goal) -> Progress:
    """Completion is observed ticket state, never the actor's self-assessment."""
    validate_scope(tickets, goal)
    pending = tuple(t for t in tickets if t.ticket_id in goal.required_ticket_ids and not t.triaged)
    done = len(goal.required_ticket_ids) - len(pending)
    return Progress(done, len(goal.required_ticket_ids), done / len(goal.required_ticket_ids),
                    tuple(t.ticket_id for t in pending), sum(t.priority == "high" for t in pending),
                    sum(1 if t.context_ready else 2 for t in pending))


def apply_action(tickets: tuple[Ticket, ...], goal: Goal, action: Action) -> tuple[tuple[Ticket, ...], Observation]:
    """Apply one allowlisted action to a copy of the fictional environment."""
    validate_scope(tickets, goal)
    if not isinstance(action, Action) or action.ticket_id not in goal.required_ticket_ids:
        raise ValueError("Action must target a ticket within the fixed goal")
    ticket = next(t for t in tickets if t.ticket_id == action.ticket_id)
    if ticket.triaged:
        return tickets, Observation("no_change", "Ticket was already triaged.")
    if action.kind == "collect_context":
        if ticket.context_ready:
            return tickets, Observation("no_change", "Context was already available.")
        if not ticket.context_available:
            return tickets, Observation("blocked", "No context exists in the demo fixture; human input is needed.")
        updated = replace(ticket, context_ready=True)
        observation = Observation("success", "Collected context from the simulated fixture.")
    else:
        if not ticket.context_ready:
            return tickets, Observation("blocked", "Collect missing context before triage.")
        updated = replace(ticket, triaged=True)
        observation = Observation("success", "Marked triaged in memory; no customer issue was resolved.")
    return tuple(updated if t.ticket_id == ticket.ticket_id else t for t in tickets), observation


def choose_action(goal: Goal, tickets: tuple[Ticket, ...], progress: Progress,
                  history: tuple[Step, ...]) -> Action:
    """Prefer pending high-priority tickets, collecting missing context first."""
    pending = [t for t in tickets if t.ticket_id in progress.pending_ids]
    ticket = min(pending, key=lambda t: (t.priority != "high", t.ticket_id))
    return Action("triage" if ticket.context_ready else "collect_context", ticket.ticket_id)


def run_goal(tickets: tuple[Ticket, ...], goal: Goal, *,
             chooser: Callable = choose_action, clock: Callable[[], float] = time.monotonic) -> GoalResult:
    """Observe → choose → act → measure → adapt, bounded by steps/stalls/time.

    Deadline checks are cooperative, before and after callbacks; they cannot
    forcibly interrupt a blocking chooser. Callers must also bound I/O timeouts.
    """
    progress = measure(tickets, goal)
    last_clock = None
    def now():
        nonlocal last_clock
        try:
            value = clock()
            valid = (type(value) in (int, float) and math.isfinite(value)
                     and (last_clock is None or value >= last_clock))
        except Exception:
            valid = False
        if not valid:
            raise ValueError("Clock must return finite, nondecreasing numbers") from None
        last_clock = value
        return value
    started = now()
    history: list[Step] = []
    stalled = 0

    def finish(status: str, reason: str) -> GoalResult:
        return GoalResult(status, reason, goal, progress, tuple(history), tickets)

    if not progress.pending_ids:
        return finish("completed", "All required tickets were already triaged.")
    for number in range(1, goal.max_steps + 1):
        if now() - started >= goal.deadline_seconds:
            return finish("deadline_exceeded", "Time budget reached before the next action.")
        action = chooser(goal, tickets, progress, tuple(history))
        if now() - started >= goal.deadline_seconds:
            return finish("deadline_exceeded", "Time budget reached while selecting an action; action was not applied.")
        tickets, observation = apply_action(tickets, goal, action)
        current = measure(tickets, goal)
        stalled = stalled + 1 if current.remaining_work >= progress.remaining_work else 0
        progress = current
        history.append(Step(number, action, observation, progress, stalled))
        if now() - started >= goal.deadline_seconds:
            return finish("deadline_exceeded", "Time budget reached; review observed progress before continuing.")
        if not progress.pending_ids:
            return finish("completed", "All required tickets were triaged within the budgets.")
        if stalled >= goal.max_stalled_steps:
            return finish("stalled", "No progress across consecutive actions; request human input.")
    return finish("step_limit", "Action budget reached with required tickets still pending.")


def demo_tickets(*, missing_context: bool = False) -> tuple[Ticket, ...]:
    return (Ticket("T-101", "high", context_ready=not missing_context),
            Ticket("T-102", "high"), Ticket("T-103"))


def print_run(result: GoalResult) -> None:
    print(f"Goal: triage {result.progress.target} required demo tickets")
    print(f"Budget: {result.goal.max_steps} actions, {result.goal.deadline_seconds:g} seconds")
    for step in result.history:
        print(f"Step {step.number}: {step.action.kind}({step.action.ticket_id}) -> {step.observation.status}"
              f" | triaged {step.progress.triaged}/{step.progress.target}"
              f" | high-priority pending {step.progress.high_priority_pending}")
    print(f"Result: {result.status} — {result.reason}")
    print("Pending:", list(result.progress.pending_ids))
    print("Simulated data only; no API call, message, or real ticket update.")


if __name__ == "__main__":
    queue = demo_tickets(missing_context=True)
    result = run_goal(queue, Goal(tuple(t.ticket_id for t in queue)))
    print(json.dumps(asdict(result), indent=2))
