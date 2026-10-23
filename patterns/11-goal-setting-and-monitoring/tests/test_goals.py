"""Observe real simulator state, adaptation, stalls, and deadline boundaries."""
from dataclasses import FrozenInstanceError
import importlib

import pytest

app = importlib.import_module("patterns.11-goal-setting-and-monitoring.app")


def test_basic_goal_reaches_measured_completion_without_mutating_input():
    tickets = app.demo_tickets()
    result = app.run_goal(tickets, app.Goal(tuple(t.ticket_id for t in tickets)))
    assert result.status == "completed" and len(result.history) == 3
    assert result.progress.completed_fraction == 1 and not result.progress.pending_ids
    assert [s.action.ticket_id for s in result.history] == ["T-101", "T-102", "T-103"]
    assert [s.progress.triaged for s in result.history] == [1, 2, 3]
    assert all(t.triaged for t in result.tickets) and not any(t.triaged for t in tickets)
    assert result.source == "simulated demo data"


def test_blocked_action_is_observed_and_next_action_adapts():
    advanced = importlib.import_module("patterns.11-goal-setting-and-monitoring.examples.advanced_example")
    tickets = app.demo_tickets(missing_context=True)
    goal = app.Goal(tuple(t.ticket_id for t in tickets))
    result = app.run_goal(tickets, goal, chooser=advanced.try_then_adapt)
    assert result.status == "completed" and len(result.history) == 5
    first, second, third = result.history[:3]
    assert first.observation.status == "blocked" and first.progress.triaged == 0
    assert second.action.kind == "collect_context" and second.progress.triaged == 0
    assert second.progress.remaining_work < first.progress.remaining_work
    assert second.stalled_steps == 0 and third.progress.triaged == 1


def test_missing_context_cannot_be_invented_and_stops_for_human_input():
    ticket = app.Ticket("T-1", "high", context_ready=False, context_available=False)
    result = app.run_goal((ticket,), app.Goal(("T-1",)))
    assert result.status == "stalled" and len(result.history) == 2
    assert all(s.observation.status == "blocked" for s in result.history)
    assert result.progress.completed_fraction == 0 and result.tickets == (ticket,)
    assert "human input" in result.reason


def test_step_limit_is_not_completion():
    queue = app.demo_tickets()
    result = app.run_goal(queue, app.Goal(tuple(t.ticket_id for t in queue), max_steps=1))
    assert result.status == "step_limit" and result.progress.triaged == 1
    assert result.progress.pending_ids == ("T-102", "T-103")


def test_repeated_no_change_counts_as_stall():
    queue = (app.Ticket("T-1"),)
    result = app.run_goal(queue, app.Goal(("T-1",)),
                          chooser=lambda *args: app.Action("collect_context", "T-1"))
    assert result.status == "stalled" and len(result.history) == 2
    assert all(s.observation.status == "no_change" for s in result.history)


def test_existing_completion_avoids_chooser():
    def forbidden(*args):
        pytest.fail("No chooser is needed for an already met goal")
    result = app.run_goal((app.Ticket("T-1", triaged=True),), app.Goal(("T-1",)), chooser=forbidden)
    assert result.status == "completed" and not result.history


def test_scope_ignores_other_tickets_and_forbids_actions_against_them():
    queue = (app.Ticket("T-1"), app.Ticket("outside", "high"))
    goal = app.Goal(("T-1",))
    result = app.run_goal(queue, goal)
    assert result.status == "completed" and not result.tickets[1].triaged
    with pytest.raises(ValueError, match="fixed goal"):
        app.run_goal(queue, goal, chooser=lambda *args: app.Action("triage", "outside"))


@pytest.mark.parametrize("ticks,expected_steps", [([0, 30], 0), ([0, 0, 30], 0), ([0, 0, 0, 30], 1)])
def test_deadline_before_selection_after_selection_and_after_action(ticks, expected_steps):
    clock = iter(ticks)
    result = app.run_goal((app.Ticket("T-1"),), app.Goal(("T-1",)), clock=lambda: next(clock))
    assert result.status == "deadline_exceeded" and len(result.history) == expected_steps
    # A late completed state is reported honestly, without claiming on-time success.
    assert result.progress.triaged == expected_steps


def test_callback_receives_immutable_goal_state_and_history():
    def inspect(goal, tickets, progress, history):
        with pytest.raises(FrozenInstanceError):
            goal.max_steps = 100
        with pytest.raises(FrozenInstanceError):
            tickets[0].triaged = True
        with pytest.raises(FrozenInstanceError):
            progress.triaged = 1
        assert isinstance(history, tuple)
        return app.Action("triage", "T-1")
    assert app.run_goal((app.Ticket("T-1"),), app.Goal(("T-1",)), chooser=inspect).status == "completed"


def test_invalid_action_and_chooser_failure_propagate_without_input_mutation():
    tickets = (app.Ticket("T-1"),)
    with pytest.raises(ValueError):
        app.run_goal(tickets, app.Goal(("T-1",)), chooser=lambda *args: {"completed": True})
    def fail(*args):
        raise RuntimeError("chooser unavailable")
    with pytest.raises(RuntimeError, match="unavailable"):
        app.run_goal(tickets, app.Goal(("T-1",)), chooser=fail)
    assert not tickets[0].triaged


@pytest.mark.parametrize("fields", [
    {"required_ticket_ids": ()}, {"required_ticket_ids": ["T-1"]},
    {"required_ticket_ids": ("T-1", "T-1")}, {"required_ticket_ids": ("",)},
    {"required_ticket_ids": tuple(str(i) for i in range(21))},
    {"max_steps": 0}, {"max_steps": True}, {"max_steps": 21},
    {"max_stalled_steps": 0}, {"max_stalled_steps": 2.5},
    {"deadline_seconds": 0}, {"deadline_seconds": -1}, {"deadline_seconds": True},
    {"deadline_seconds": float("nan")}, {"deadline_seconds": float("inf")}, {"deadline_seconds": 301},
])
def test_invalid_goal(fields):
    with pytest.raises(ValueError):
        app.Goal(**({"required_ticket_ids": ("T-1",)} | fields))


@pytest.mark.parametrize("queue", [(), [], ("T-1",),
    (app.Ticket("T-1"), app.Ticket("T-1")), (app.Ticket("T-2"),)])
def test_invalid_scope(queue):
    with pytest.raises(ValueError):
        app.run_goal(queue, app.Goal(("T-1",)))


@pytest.mark.parametrize("fields", [{"ticket_id": ""}, {"priority": "urgent"},
    {"context_ready": 1}, {"triaged": "yes"}, {"context_ready": False, "triaged": True}])
def test_invalid_ticket_state(fields):
    with pytest.raises(ValueError):
        app.Ticket(**({"ticket_id": "T-1"} | fields))


def test_success_on_final_allowed_step_and_already_triaged_no_change():
    goal = app.Goal(("T-1",), max_steps=1)
    result = app.run_goal((app.Ticket("T-1"),), goal)
    assert result.status == "completed"
    unchanged, observation = app.apply_action(result.tickets, goal, app.Action("triage", "T-1"))
    assert unchanged == result.tickets and observation.status == "no_change"


@pytest.mark.parametrize("bad", [float("nan"),float("inf"),float("-inf"),True,"invalid",10**400])
def test_invalid_clock_never_applies_an_action(bad):
    tickets = (app.Ticket("T-1"),)
    ticks = iter([0,0,bad])
    with pytest.raises(ValueError, match="Clock"):
        app.run_goal(tickets, app.Goal(("T-1",)), clock=lambda:next(ticks))
    assert not tickets[0].triaged


def test_clock_rollback_after_selection_does_not_apply_action():
    tickets = (app.Ticket("T-1"),)
    ticks = iter([10,10,9])
    with pytest.raises(ValueError, match="Clock"):
        app.run_goal(tickets, app.Goal(("T-1",)), clock=lambda:next(ticks))
    assert not tickets[0].triaged
