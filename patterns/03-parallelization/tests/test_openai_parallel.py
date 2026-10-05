"""Fake async SDK tests; real API calls and credentials are never used."""
import asyncio
from importlib import import_module
import sys
import types

import pytest

parallel = import_module("patterns.03-parallelization.openai_version.openai_parallel")


@pytest.fixture
def fake_async_openai(monkeypatch):
    def install(overrides=None):
        overrides = overrides or {}
        requests = []
        state = {"closed": False, "client_options": None}

        class FakeClient:
            def __init__(self, **kwargs):
                state["client_options"] = kwargs
                self.responses = self
                self.all_started = asyncio.Event()

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                state["closed"] = True

            async def create(self, **kwargs):
                requests.append(kwargs)
                if len(requests) == 3:
                    self.all_started.set()
                # A sequential implementation would deadlock here and time out.
                await self.all_started.wait()
                name = next(name for name, prompt in parallel.TASK_PROMPTS.items()
                            if prompt == kwargs["instructions"])
                output = overrides.get(name, f"{name} analysis")
                if isinstance(output, Exception):
                    raise output
                if output == "stall":
                    await asyncio.Event().wait()
                if output == "incomplete":
                    return types.SimpleNamespace(status="incomplete", output_text="partial")
                return types.SimpleNamespace(status="completed", output_text=output)

        monkeypatch.setitem(sys.modules, "openai", types.SimpleNamespace(AsyncOpenAI=FakeClient))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-test-placeholder")
        return requests, state
    return install


def test_three_requests_are_concurrent_and_client_is_closed(fake_async_openai):
    requests, state = fake_async_openai()
    result = asyncio.run(asyncio.wait_for(parallel.run_openai_parallel("original ticket"), timeout=1))
    assert [task.status for task in result.task_results] == ["success"] * 3
    assert len(requests) == 3
    assert {request["input"] for request in requests} == {"original ticket"}
    assert {request["instructions"] for request in requests} == set(parallel.TASK_PROMPTS.values())
    assert all(request["model"] == "gpt-6-astra" for request in requests)
    assert all(request["reasoning"] == {"effort": "low"} for request in requests)
    assert all("temperature" not in request for request in requests)
    assert state["client_options"]["max_retries"] == 0
    assert state["closed"]
    assert "summary: summary analysis" in result.combined_response


@pytest.mark.parametrize("env,explicit,expected", [
    ("gpt-6.1-sol", None, "gpt-6.1-sol"),
    ("env-model", "explicit-model", "explicit-model"),
    (" ", None, "gpt-6-astra"),
])
def test_model_selection(fake_async_openai, monkeypatch, env, explicit, expected):
    requests, _ = fake_async_openai()
    monkeypatch.setenv("OPENAI_MODEL", env)
    asyncio.run(parallel.run_openai_parallel("ticket", model=explicit))
    assert [request["model"] for request in requests] == [expected] * 3


def test_missing_api_key_is_clear():
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        asyncio.run(parallel.run_openai_parallel("ticket"))


def test_blank_query_does_not_make_requests(fake_async_openai):
    requests, state = fake_async_openai()
    with pytest.raises(ValueError, match="non-empty"):
        asyncio.run(parallel.run_openai_parallel(" "))
    assert requests == []
    assert state["client_options"] is None


@pytest.mark.parametrize("output", [None, "", "incomplete", RuntimeError("API unavailable")])
def test_unusable_branch_keeps_other_outputs(fake_async_openai, output):
    _, state = fake_async_openai({"urgency": output})
    result = asyncio.run(parallel.run_openai_parallel("ticket"))
    assert [task.status for task in result.task_results] == ["success", "success", "error"]
    assert result.task_results[2].output is None
    assert "summary: summary analysis" in result.combined_response
    assert "urgency: unavailable (error)" in result.combined_response
    assert state["closed"]


def test_request_timeout_retains_completed_branches(fake_async_openai):
    _, state = fake_async_openai({"urgency": "stall"})
    result = asyncio.run(parallel.run_openai_parallel("ticket", task_timeout=0.01))
    assert [task.status for task in result.task_results] == ["success", "success", "timeout"]
    assert state["closed"]


def test_all_failed_requests_do_not_produce_fabricated_analysis(fake_async_openai):
    fake_async_openai({name: RuntimeError("API unavailable") for name in parallel.TASK_PROMPTS})
    result = asyncio.run(parallel.run_openai_parallel("ticket"))
    assert all(task.status == "error" and task.output is None for task in result.task_results)
    assert result.combined_response.count("unavailable") == 3
