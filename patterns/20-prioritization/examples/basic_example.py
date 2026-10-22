"""Rank one snapshot, then simulate work within a fixed budget."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import demo_tasks, print_decision, prioritize, simulate

if __name__ == "__main__":
    tasks = demo_tasks()
    resources = ("general", "analytics")
    print("Free local example: 25 simulated work minutes.")
    print_decision(prioritize(tasks, budget_minutes=25, resources=resources))
    run = simulate(tasks, budget_minutes=25, resources=resources)
    for step in run.steps:
        print(f"SIMULATED {step.started_minute:02d}-{step.finished_minute:02d}m: {step.title}; budget left={step.remaining_budget}m")
    print("Stop:", run.stop_reason, "| Pending:", ", ".join(run.pending) or "none")
