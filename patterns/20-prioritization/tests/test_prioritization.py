"""Offline checks for ranking, feasibility, dynamic changes, and honest stopping."""
import importlib
from dataclasses import replace
import json
import random

import pytest

app = importlib.import_module("patterns.20-prioritization.app")
RESOURCES = ("general", "analytics")


def task(task_id="one", **kwargs):
    return app.Task(task_id, kwargs.pop("title", "Fictional work"), kwargs.pop("importance", 3),
                    kwargs.pop("effort_minutes", 5), **kwargs)


def test_basic_ranking_exposes_components_and_blocks_dependency():
    result = app.prioritize(app.demo_tasks(), budget_minutes=25, resources=RESOURCES)
    assert result.selected_task_id == "metrics"
    assert [r.task_id for r in result.ranked] == ["metrics", "notes", "feedback"]
    metrics = result.ranked[0]
    assert (metrics.rule_score, metrics.importance_points, metrics.urgency_points,
            metrics.aging_points, metrics.unlock_points) == (27, 16, 9, 0, 2)
    assert result.unavailable == (app.UnavailableTask("fix", ("dependencies_pending",)),)


def test_dependency_completion_changes_next_choice():
    result = app.prioritize(app.demo_tasks(), completed=("metrics",), now_minute=5,
                            budget_minutes=20, resources=RESOURCES)
    assert result.selected_task_id == "fix"
    assert "metrics" not in [r.task_id for r in result.ranked]


def test_due_time_changes_order_at_same_budget():
    tasks = [task("important", importance=4), task("urgent", importance=2, due_minute=100)]
    assert app.prioritize(tasks).selected_task_id == "important"
    assert app.prioritize(tasks, now_minute=95).selected_task_id == "urgent"


@pytest.mark.parametrize("remaining,expected", [(-1,5),(0,5),(1,4),(10,4),(11,3),(30,3),(31,2),(60,2),(61,1)])
def test_soft_deadline_boundaries(remaining, expected):
    assert app.urgency(task(due_minute=100), 100-remaining) == expected
    assert app.urgency(task(), 1000) == 0


def test_aging_is_bounded_and_tie_breaks_are_deterministic():
    old, new = task("old"), task("new", created_minute=90)
    result = app.prioritize([new, old], now_minute=90)
    assert result.selected_task_id == "old"
    assert result.ranked[0].aging_points == 5
    tasks = [task("beta"), task("alpha"), task("short", effort_minutes=1)]
    forward = app.prioritize(tasks)
    backward = app.prioritize(list(reversed(tasks)))
    assert [r.task_id for r in forward.ranked] == ["short", "alpha", "beta"]
    assert forward == backward


def test_unlock_bonus_counts_arrived_unfinished_direct_dependents_only():
    tasks = [task("root")] + [task(f"child{i}", dependencies=("root",)) for i in range(4)]
    tasks += [task("future", created_minute=90, dependencies=("root",))]
    assert app.prioritize(tasks).ranked[0].unlock_points == 6
    # A root can be a prerequisite without immediately unlocking a multi-dependency child.
    tasks = [task("root"), task("other"), task("child", dependencies=("root", "other"))]
    result = app.prioritize(tasks)
    assert all(r.unlock_points == 2 for r in result.ranked)


def test_unavailable_reasons_and_no_head_of_line_budget_block():
    tasks = [task("expensive", importance=5, effort_minutes=20), task("small", importance=1, effort_minutes=3),
             task("blocked", created_minute=5, dependencies=("small",), resource="reporting")]
    result = app.prioritize(tasks, budget_minutes=3)
    assert result.selected_task_id == "small"
    assert {v.task_id:v.reasons for v in result.unavailable} == {
        "expensive":("over_budget",), "blocked":("not_arrived","dependencies_pending","resource_unavailable","over_budget")}


def test_resource_arrival_and_budget_changes_are_rechecked():
    tasks = [task(resource="reporting", created_minute=5)]
    assert app.prioritize(tasks, now_minute=4, resources=("reporting",)).status == "blocked"
    assert app.prioritize(tasks, now_minute=5).status == "blocked"
    assert app.prioritize(tasks, now_minute=5, resources=("reporting",), budget_minutes=4).status == "blocked"
    assert app.prioritize(tasks, now_minute=5, resources=("reporting",), budget_minutes=5).selected_task_id == "one"


def test_empty_completed_and_blocked_backlogs_are_distinct():
    assert app.prioritize([]).status == "complete"
    assert app.prioritize([task()], completed=("one",)).reason_code == "all_completed"
    blocked = app.prioritize([task()], budget_minutes=0)
    assert blocked.status == "blocked" and blocked.reason_code == "no_eligible_tasks"
    assert blocked.selected_task_id is None
    assert app.prioritize([task()], resources=()).status == "blocked"


def test_basic_simulation_budget_and_pending_work():
    tasks = app.demo_tasks()
    result = app.simulate(tasks, budget_minutes=25, resources=RESOURCES)
    assert [s.task_id for s in result.steps] == ["metrics", "fix", "notes"]
    assert result.remaining_budget == 0 and result.now_minute == 25
    assert result.pending == ("feedback",)
    assert result.stop_reason == "no_eligible_tasks"
    assert tasks == app.demo_tasks()  # Input records were not mutated.


def test_new_urgent_arrival_reorders_next_decision_without_preemption():
    tasks = app.demo_tasks() + (task("incident", importance=5, effort_minutes=7, created_minute=5, due_minute=8),
                                task("dashboard", effort_minutes=4, resource="reporting"))
    result = app.simulate(tasks, budget_minutes=30, resources=RESOURCES)
    assert [s.task_id for s in result.steps] == ["metrics", "incident", "fix", "feedback"]
    assert result.steps[1].started_minute == 5
    assert result.steps[2].lateness_minutes == 4
    assert result.pending == ("dashboard", "notes")
    assert result.steps[-1].remaining_budget == 0


def test_simulation_stop_reasons_and_no_implicit_waiting():
    assert app.simulate([]).stop_reason == "all_completed"
    assert app.simulate([task()], budget_minutes=5).stop_reason == "all_completed"
    assert app.simulate([task()], max_steps=0).stop_reason == "step_limit"
    assert app.simulate([task()], max_steps=1).stop_reason == "all_completed"
    future = app.simulate([task(created_minute=5)], budget_minutes=30)
    assert future.stop_reason == "no_eligible_tasks" and future.now_minute == 0
    assert future.remaining_budget == 30 and not future.steps


@pytest.mark.parametrize("seed", range(8))
def test_simulation_invariants_across_small_dags(seed):
    rng = random.Random(seed)
    tasks = []
    for i in range(8):
        deps = tuple(t.task_id for t in tasks if rng.random() < .2)
        tasks.append(task(f"t{i}", importance=rng.randint(1,5), effort_minutes=rng.randint(1,15),
                          created_minute=rng.randint(0,10), dependencies=deps,
                          resource=rng.choice(app.RESOURCES)))
    budget = 45
    result = app.simulate(tasks, budget_minutes=budget, resources=RESOURCES, max_steps=8)
    done = set()
    by_id = {t.task_id:t for t in tasks}
    previous_finish = 0
    for step in result.steps:
        current = by_id[step.task_id]
        assert current.task_id not in done and set(current.dependencies) <= done
        assert current.resource in RESOURCES and current.created_minute <= step.started_minute
        assert step.started_minute == previous_finish
        assert step.finished_minute-step.started_minute == current.effort_minutes
        budget -= current.effort_minutes
        assert step.remaining_budget == budget >= 0
        previous_finish = step.finished_minute
        done.add(current.task_id)
    assert done == set(result.completed)
    assert done.isdisjoint(result.pending)
    assert done | set(result.pending) == set(by_id)


@pytest.mark.parametrize("changes", [{"task_id":"BAD ID"},{"title":" "},{"title":"x"*161},
    {"importance":True},{"importance":0},{"importance":6},{"effort_minutes":0},{"effort_minutes":121},
    {"effort_minutes":1.5},{"created_minute":-1},{"created_minute":True},{"due_minute":-1},
    {"due_minute":False},{"created_minute":10,"due_minute":5},{"dependencies":["x"]},
    {"dependencies":("one",)},{"dependencies":("x","x")},{"dependencies":([], )},{"resource":"unknown"}])
def test_invalid_task_records(changes):
    values = {"task_id":"one","title":"Work","importance":3,"effort_minutes":5}
    values.update(changes)
    with pytest.raises(ValueError):
        app.Task(**values)


@pytest.mark.parametrize("tasks", [[], [None]])
def test_backlog_record_types(tasks):
    if tasks:
        with pytest.raises(ValueError):
            app.prioritize(tasks)
    else:
        assert app.prioritize(tasks).status == "complete"


def test_graph_errors_duplicate_ids_unknown_edges_and_cycles():
    invalid = [[task(),task()], [task(dependencies=("missing",))],
               [task("a",dependencies=("b",)),task("b",dependencies=("a",))],
               [task(f"t{i}") for i in range(21)]]
    for tasks in invalid:
        with pytest.raises(ValueError):
            app.prioritize(tasks)


@pytest.mark.parametrize("kwargs", [{"completed":("missing",)},{"completed":("one","one")},
    {"completed":[[]]},{"now_minute":-1},{"now_minute":True},{"budget_minutes":-1},
    {"budget_minutes":481},{"budget_minutes":True},{"resources":("unknown",)},
    {"resources":("general","general")},{"resources":[[]]}])
def test_invalid_snapshot_context(kwargs):
    with pytest.raises(ValueError):
        app.prioritize([task()], **kwargs)


def test_completed_context_cannot_claim_unfinished_prerequisites_or_future_work():
    with pytest.raises(ValueError, match="prerequisites"):
        app.prioritize([task("root"),task(dependencies=("root",))], completed=("one",))
    with pytest.raises(ValueError, match="arrived"):
        app.prioritize([task(created_minute=10)], completed=("one",))


@pytest.mark.parametrize("max_steps", [-1,21,True,1.5,None])
def test_invalid_step_limits(max_steps):
    with pytest.raises(ValueError):
        app.simulate([task()], max_steps=max_steps)


def test_model_can_reorder_only_exact_current_eligible_set():
    snapshot = app.prioritize(app.demo_tasks(), resources=RESOURCES)
    ranked = app.apply_model_ranking(snapshot,["feedback","notes","metrics"])
    assert ranked.selected_task_id == "feedback" and ranked.ranking_source == "openai"
    assert ranked.ranked[0].rule_score == 4  # Host diagnostics remain unchanged.
    assert snapshot.selected_task_id == "metrics"
    for invalid in [["fix","notes","metrics"],["feedback","notes","invented"],
                    ["metrics","metrics","feedback"],["metrics"],None,[{},"notes","metrics"]]:
        with pytest.raises(ValueError):
            app.apply_model_ranking(snapshot,invalid)


def test_cli_outputs_simulation_and_rejects_invalid_budget(monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",["app.py","--budget-minutes","0"])
    app.main()
    assert '"stop_reason": "no_eligible_tasks"' in capsys.readouterr().out
    monkeypatch.setattr("sys.argv",["app.py","--budget-minutes","-1"])
    with pytest.raises(SystemExit,match="Budget"):
        app.main()
