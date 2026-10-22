"""Choose the next feasible task from a bounded backlog; execute only a simulation."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass, replace
import json
import re

RESOURCES = ("general", "analytics", "reporting")


def nonnegative_integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative integer")


@dataclass(frozen=True)
class Task:
    task_id: str
    title: str
    importance: int
    effort_minutes: int
    created_minute: int = 0
    due_minute: int | None = None
    dependencies: tuple[str, ...] = ()
    resource: str = "general"

    def __post_init__(self):
        if not isinstance(self.task_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,31}", self.task_id):
            raise ValueError("Invalid task ID")
        if not isinstance(self.title, str) or not 1 <= len(self.title) <= 160 or not self.title.strip():
            raise ValueError("Task title must contain 1 to 160 characters")
        if type(self.importance) is not int or not 1 <= self.importance <= 5:
            raise ValueError("Importance must be an integer from 1 to 5")
        if type(self.effort_minutes) is not int or not 1 <= self.effort_minutes <= 120:
            raise ValueError("Effort must be an integer from 1 to 120 minutes")
        nonnegative_integer(self.created_minute, "created_minute")
        if self.due_minute is not None:
            nonnegative_integer(self.due_minute, "due_minute")
            if self.due_minute < self.created_minute:
                raise ValueError("A deadline cannot precede task creation")
        if (not isinstance(self.dependencies, tuple) or len(self.dependencies) > 19
                or any(not isinstance(d, str) for d in self.dependencies)
                or len(set(self.dependencies)) != len(self.dependencies) or self.task_id in self.dependencies):
            raise ValueError("Dependencies must be unique other task IDs in a tuple")
        if self.resource not in RESOURCES:
            raise ValueError("Unknown resource")


@dataclass(frozen=True)
class RankedTask:
    task_id: str
    title: str
    rule_score: int
    importance_points: int
    urgency_points: int
    aging_points: int
    unlock_points: int
    effort_minutes: int
    due_minute: int | None


@dataclass(frozen=True)
class UnavailableTask:
    task_id: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class Decision:
    status: str
    selected_task_id: str | None
    ranking_source: str
    reason_code: str
    ranked: tuple[RankedTask, ...]
    unavailable: tuple[UnavailableTask, ...]


@dataclass(frozen=True)
class Step:
    task_id: str
    title: str
    started_minute: int
    finished_minute: int
    rule_score: int
    lateness_minutes: int | None
    remaining_budget: int


@dataclass(frozen=True)
class Simulation:
    stop_reason: str
    steps: tuple[Step, ...]
    completed: tuple[str, ...]
    pending: tuple[str, ...]
    now_minute: int
    remaining_budget: int
    final_decision: Decision


def validate_snapshot(tasks, completed=(), *, now_minute=0, budget_minutes=30, resources=("general",)):
    if (not isinstance(tasks, (tuple, list)) or len(tasks) > 20
            or any(not isinstance(task, Task) for task in tasks)):
        raise ValueError("Provide at most 20 Task records")
    tasks = tuple(tasks)
    by_id = {task.task_id: task for task in tasks}
    if len(by_id) != len(tasks):
        raise ValueError("Task IDs must be unique")
    for task in tasks:
        if any(dep not in by_id for dep in task.dependencies):
            raise ValueError("Every dependency must exist in the backlog")
    visiting, visited = set(), set()
    def visit(task_id):
        if task_id in visiting:
            raise ValueError("Dependency cycle detected")
        if task_id not in visited:
            visiting.add(task_id)
            for dep in by_id[task_id].dependencies:
                visit(dep)
            visiting.remove(task_id)
            visited.add(task_id)
    for task in tasks:
        visit(task.task_id)
    nonnegative_integer(now_minute, "now_minute")
    if type(budget_minutes) is not int or not 0 <= budget_minutes <= 480:
        raise ValueError("Budget must be an integer from 0 to 480 minutes")
    if (not isinstance(completed, (tuple, list)) or len(completed) > 20
            or any(not isinstance(v, str) for v in completed)
            or len(set(completed)) != len(completed) or any(v not in by_id for v in completed)):
        raise ValueError("Completed IDs must be unique backlog task IDs")
    done = set(completed)
    if any(by_id[v].created_minute > now_minute or not set(by_id[v].dependencies) <= done for v in done):
        raise ValueError("Completed tasks must have arrived and have completed prerequisites")
    if (not isinstance(resources, (tuple, list)) or len(resources) > len(RESOURCES)
            or any(r not in RESOURCES for r in resources) or len(set(resources)) != len(resources)):
        raise ValueError("Resources must be a unique tuple/list of known resource names")
    return tasks, frozenset(done), frozenset(resources)


def urgency(task: Task, now_minute: int) -> int:
    if task.due_minute is None:
        return 0
    minutes_left = task.due_minute - now_minute
    if minutes_left <= 0:
        return 5
    if minutes_left <= 10:
        return 4
    if minutes_left <= 30:
        return 3
    if minutes_left <= 60:
        return 2
    return 1


def prioritize(tasks, *, completed=(), now_minute=0, budget_minutes=30,
               resources=("general",)) -> Decision:
    tasks, done, resources = validate_snapshot(tasks, completed, now_minute=now_minute,
                                               budget_minutes=budget_minutes, resources=resources)
    ranked, unavailable = [], []
    for task in tasks:
        if task.task_id in done:
            continue
        reasons = []
        if task.created_minute > now_minute:
            reasons.append("not_arrived")
        if not set(task.dependencies) <= done:
            reasons.append("dependencies_pending")
        if task.resource not in resources:
            reasons.append("resource_unavailable")
        if task.effort_minutes > budget_minutes:
            reasons.append("over_budget")
        if reasons:
            unavailable.append(UnavailableTask(task.task_id, tuple(reasons)))
            continue
        importance_points = 4 * task.importance
        urgency_points = 3 * urgency(task, now_minute)
        aging_points = min((now_minute - task.created_minute) // 15, 5)
        # Reward immediate prerequisites of unfinished tasks that have already arrived.
        children = sum(task.task_id in other.dependencies and other.task_id not in done
                       and other.created_minute <= now_minute for other in tasks)
        unlock_points = 2 * min(children, 3)
        score = importance_points + urgency_points + aging_points + unlock_points
        ranked.append(RankedTask(task.task_id, task.title, score, importance_points, urgency_points,
                                 aging_points, unlock_points, task.effort_minutes, task.due_minute))
    ranked.sort(key=lambda item: (-item.rule_score, item.effort_minutes, item.task_id))
    unavailable.sort(key=lambda item: item.task_id)
    status = "selected" if ranked else "complete" if len(done) == len(tasks) else "blocked"
    return Decision(status, ranked[0].task_id if ranked else None, "rules",
                    "highest_rule_score" if ranked else "all_completed" if status == "complete" else "no_eligible_tasks",
                    tuple(ranked), tuple(unavailable))


def apply_model_ranking(decision: Decision, ordered_ids) -> Decision:
    """Only an exact permutation of this snapshot's eligible IDs is accepted."""
    eligible = {item.task_id: item for item in decision.ranked}
    if (not eligible or not isinstance(ordered_ids, list) or len(ordered_ids) != len(eligible)
            or any(not isinstance(task_id, str) for task_id in ordered_ids)
            or len(set(ordered_ids)) != len(ordered_ids) or set(ordered_ids) != set(eligible)):
        raise ValueError("Model ranking must contain every eligible task ID exactly once")
    return replace(decision, selected_task_id=ordered_ids[0], ranking_source="openai",
                   reason_code="validated_model_ranking", ranked=tuple(eligible[v] for v in ordered_ids))


def simulate(tasks, *, completed=(), now_minute=0, budget_minutes=30,
             resources=("general",), max_steps=6) -> Simulation:
    """Single-worker, non-preemptive simulation; no task causes a real action."""
    tasks, done, resources = validate_snapshot(tasks, completed, now_minute=now_minute,
                                               budget_minutes=budget_minutes, resources=resources)
    if type(max_steps) is not int or not 0 <= max_steps <= 20:
        raise ValueError("max_steps must be an integer from 0 to 20")
    done = set(done)
    by_id = {task.task_id: task for task in tasks}
    steps = []
    for _ in range(max_steps):
        decision = prioritize(tasks, completed=tuple(done), now_minute=now_minute,
                              budget_minutes=budget_minutes, resources=tuple(resources))
        if decision.selected_task_id is None:
            break
        task = by_id[decision.selected_task_id]
        started = now_minute
        now_minute += task.effort_minutes
        budget_minutes -= task.effort_minutes
        done.add(task.task_id)
        steps.append(Step(task.task_id, task.title, started, now_minute,
                          decision.ranked[0].rule_score,
                          max(0, now_minute - task.due_minute) if task.due_minute is not None else None,
                          budget_minutes))
    final = prioritize(tasks, completed=tuple(done), now_minute=now_minute,
                       budget_minutes=budget_minutes, resources=tuple(resources))
    stop = "all_completed" if final.status == "complete" else "no_eligible_tasks" if final.status == "blocked" else "step_limit"
    return Simulation(stop, tuple(steps), tuple(sorted(done)),
                      tuple(sorted(task.task_id for task in tasks if task.task_id not in done)),
                      now_minute, budget_minutes, final)


def demo_tasks() -> tuple[Task, ...]:
    return (
        Task("metrics", "Collect release metrics", 4, 5, due_minute=25, resource="analytics"),
        Task("fix", "Fix checkout regression", 5, 12, due_minute=20, dependencies=("metrics",)),
        Task("notes", "Write release notes", 2, 8, due_minute=60),
        Task("feedback", "Summarize customer feedback", 1, 6),
    )


def print_decision(decision: Decision) -> None:
    print(f"Decision: {decision.status}; source={decision.ranking_source}; reason={decision.reason_code}")
    for index, item in enumerate(decision.ranked, 1):
        print(f"  {index}. {item.task_id}: score={item.rule_score}, effort={item.effort_minutes}m "
              f"(importance={item.importance_points}, urgency={item.urgency_points}, "
              f"aging={item.aging_points}, unlock={item.unlock_points})")
    for item in decision.unavailable:
        print(f"  Deferred {item.task_id}: {', '.join(item.reasons)}")
    print("Selected:", decision.selected_task_id or "none")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prioritize a fictional release backlog without API calls")
    parser.add_argument("--budget-minutes", type=int, default=25)
    parser.add_argument("--max-steps", type=int, default=6)
    args = parser.parse_args()
    try:
        tasks = demo_tasks()
        print("Free local prioritization; minutes and task completion are simulated.")
        print_decision(prioritize(tasks, budget_minutes=args.budget_minutes, resources=("general", "analytics")))
        result = simulate(tasks, budget_minutes=args.budget_minutes, max_steps=args.max_steps,
                          resources=("general", "analytics"))
        print(json.dumps(asdict(result), indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
