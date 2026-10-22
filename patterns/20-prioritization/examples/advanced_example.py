"""Reprioritize on arrival, dependency completion, and a shrinking work budget."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import Task, demo_tasks, print_decision, prioritize, simulate

if __name__ == "__main__":
    tasks = demo_tasks() + (
        Task("incident", "Investigate a new checkout outage", 5, 7, created_minute=5, due_minute=8),
        Task("dashboard", "Refresh the reporting dashboard", 3, 4, resource="reporting"),
    )
    resources = ("general", "analytics")
    print("Free simulation: urgent task arrives at minute 5; reporting resource is unavailable.")
    run = simulate(tasks, budget_minutes=30, resources=resources)
    completed = ()
    for step in run.steps:
        print(f"\nReprioritize at minute {step.started_minute}:")
        print_decision(prioritize(tasks, completed=completed, now_minute=step.started_minute,
                                 budget_minutes=30-step.started_minute, resources=resources))
        print(f"SIMULATED {step.task_id}: {step.started_minute}-{step.finished_minute}m; budget left={step.remaining_budget}m; lateness={step.lateness_minutes}")
        completed += (step.task_id,)
    print("\nFinal snapshot:")
    print_decision(run.final_decision)
    print("Stop:", run.stop_reason, "| Pending:", ", ".join(run.pending))
    capped = simulate(tasks, budget_minutes=30, resources=resources, max_steps=1)
    print("One-step cap:", capped.stop_reason, "| Next eligible:", capped.final_decision.selected_task_id)
