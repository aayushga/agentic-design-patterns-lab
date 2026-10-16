"""Observed failure triggers adaptation; blocked work has an honest stop."""
from pathlib import Path
import sys

if __package__:
    from ..app import Action, Goal, Ticket, choose_action, demo_tickets, print_run, run_goal
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import Action, Goal, Ticket, choose_action, demo_tickets, print_run, run_goal


def try_then_adapt(goal, tickets, progress, history):
    if not history:
        return Action("triage", "T-101")  # Demonstrate an observed unmet prerequisite.
    return choose_action(goal, tickets, progress, history)


if __name__ == "__main__":
    queue = demo_tickets(missing_context=True)
    goal = Goal(tuple(t.ticket_id for t in queue))
    print("ADAPT AFTER A BLOCKED ACTION")
    print_run(run_goal(queue, goal, chooser=try_then_adapt))
    print("\nSTOP WHEN INPUT IS UNAVAILABLE")
    print_run(run_goal((Ticket("T-201", "high", context_ready=False, context_available=False),),
                       Goal(("T-201",))))
    print("\nSTOP AT THE STEP BUDGET")
    print_run(run_goal(queue, Goal(goal.required_ticket_ids, max_steps=1)))
