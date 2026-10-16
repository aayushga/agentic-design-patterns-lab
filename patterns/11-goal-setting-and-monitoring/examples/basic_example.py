"""Meet a fixed, measurable triage goal without an API."""
from pathlib import Path
import sys

if __package__:
    from ..app import Goal, demo_tickets, print_run, run_goal
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import Goal, demo_tickets, print_run, run_goal


if __name__ == "__main__":
    tickets = demo_tickets()
    print_run(run_goal(tickets, Goal(tuple(t.ticket_id for t in tickets))))
