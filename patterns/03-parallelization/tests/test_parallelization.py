"""Offline tests of concurrency, ordering, failures, and cancellation."""
import asyncio
from dataclasses import asdict
from importlib import import_module

import pytest

app = import_module("patterns.03-parallelization.app")


def test_all_tasks_start_before_any_finishes_and_merge_runs_last(monkeypatch):
    async def scenario():
        started = []
        finished = []
        all_started = asyncio.Event()

        def make_analyzer(name):
            async def analyze(text):
                started.append((name, text))
                if len(started) == 3:
                    all_started.set()
                await all_started.wait()
                finished.append(name)
                return f"{name} output"
            return analyze

        original_combine = app.combine_results

        def checked_combine(results):
            assert len(finished) == 3
            return original_combine(results)

        monkeypatch.setattr(app, "combine_results", checked_combine)
        tasks = {name: make_analyzer(name) for name in ["summary", "keywords", "urgency"]}
        result = await asyncio.wait_for(
            app.run_parallel_analysis("original ticket", analyzers=tasks), timeout=1
        )
        assert {text for _, text in started} == {"original ticket"}
        assert [task.task for task in result.task_results] == list(tasks)
        assert all(task.status == "success" for task in result.task_results)
        assert set(asdict(result)) == {
            "original_query", "task_results", "combined_response", "elapsed_seconds"
        }
        assert "summary: summary output" in result.combined_response
    asyncio.run(scenario())


def test_result_order_is_stable_when_completion_order_changes():
    async def scenario():
        second_done = asyncio.Event()
        completed = []

        async def first(text):
            await second_done.wait()
            completed.append("first")
            return "first output"

        async def second(text):
            completed.append("second")
            second_done.set()
            return "second output"

        result = await app.run_parallel_analysis("input", analyzers={"first": first, "second": second})
        assert completed == ["second", "first"]
        assert [task.task for task in result.task_results] == ["first", "second"]
    asyncio.run(scenario())


def test_sequential_comparison_runs_one_task_at_a_time():
    async def scenario():
        events = []

        def make_analyzer(name):
            async def analyze(text):
                events.append(f"start {name}")
                await asyncio.sleep(0)
                events.append(f"end {name}")
                return name
            return analyze

        tasks = {name: make_analyzer(name) for name in ["a", "b", "c"]}
        sequential = await app.run_parallel_analysis("input", analyzers=tasks, sequential=True)
        assert events == ["start a", "end a", "start b", "end b", "start c", "end c"]
        parallel = await app.run_parallel_analysis("input", analyzers=tasks)
        assert sequential.task_results == parallel.task_results
        assert sequential.combined_response == parallel.combined_response
    asyncio.run(scenario())


def test_failed_branch_keeps_successful_results():
    async def good(text):
        return "useful result"

    async def bad(text):
        raise RuntimeError("sensitive request details")

    result = asyncio.run(app.run_parallel_analysis("input", analyzers={"good": good, "bad": bad}))
    assert [task.status for task in result.task_results] == ["success", "error"]
    assert result.task_results[1].output is None
    assert result.task_results[1].error == "Task failed (RuntimeError)"
    assert result.combined_response == "good: useful result\nbad: unavailable (error)"
    assert "sensitive" not in str(asdict(result))


def test_timed_out_branch_is_cancelled_without_losing_other_results():
    async def scenario():
        cancelled = asyncio.Event()

        async def stalled(text):
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        async def good(text):
            return "completed"

        result = await app.run_parallel_analysis(
            "input", analyzers={"good": good, "stalled": stalled}, task_timeout=0.01
        )
        assert cancelled.is_set()
        assert [task.status for task in result.task_results] == ["success", "timeout"]
        assert "good: completed" in result.combined_response
    asyncio.run(scenario())


def test_caller_cancellation_propagates_and_cancels_children():
    async def scenario():
        started = asyncio.Event()
        cancelled = asyncio.Event()

        async def stalled(text):
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()

        run = asyncio.create_task(app.run_parallel_analysis("input", analyzers={"stalled": stalled}))
        await started.wait()
        run.cancel()
        with pytest.raises(asyncio.CancelledError):
            await run
        assert cancelled.is_set()
    asyncio.run(scenario())


@pytest.mark.parametrize("output", [None, "", "  ", 42])
def test_invalid_analyzer_output_is_a_branch_error(output):
    async def analyzer(text):
        return output
    result = asyncio.run(app.run_parallel_analysis("input", analyzers={"bad": analyzer}))
    assert result.task_results[0].status == "error"
    assert result.combined_response == "bad: unavailable (error)"


@pytest.mark.parametrize("timeout", [0, -1, float("nan"), float("inf")])
def test_invalid_timeout_is_rejected(timeout):
    with pytest.raises(ValueError, match="positive, finite"):
        asyncio.run(app.run_parallel_analysis("input", task_timeout=timeout))


@pytest.mark.parametrize("query", ["", " \n "])
def test_blank_input_is_rejected(query):
    with pytest.raises(ValueError, match="non-empty"):
        asyncio.run(app.run_parallel_analysis(query))


def test_empty_task_mapping_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        asyncio.run(app.run_parallel_analysis("input", analyzers={}))


def test_local_analyzers_have_predictable_behavior(monkeypatch):
    monkeypatch.setattr(app, "DEMO_DELAY_SECONDS", 0)
    result = asyncio.run(app.run_parallel_analysis("Urgent: checkout is down. Checkout is blocked."))
    assert [task.task for task in result.task_results] == ["summary", "keywords", "urgency"]
    assert result.task_results[0].output == result.original_query
    assert result.task_results[1].output.startswith("checkout,")
    assert result.task_results[2].output.startswith("high:")
    normal = asyncio.run(app.assess_urgency("Please explain your pricing"))
    assert normal.startswith("normal:")
