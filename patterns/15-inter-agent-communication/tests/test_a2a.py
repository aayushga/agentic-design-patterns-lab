"""Offline protocol integration tests using the real A2A SDK and ASGI HTTP."""
import asyncio
import importlib
import json

import pytest
from a2a.types import CancelTaskRequest, Message, Part, Role, SendMessageRequest, TaskState
from a2a.utils.errors import TaskNotCancelableError, TaskNotFoundError

app = importlib.import_module("patterns.15-inter-agent-communication.app")
TICKET = {"skill": app.SKILL, "category": "support", "issue": "Reset link expired."}


def run(coro):
    return asyncio.run(coro)


def test_discovery_complete_artifact_and_get():
    async def scenario():
        async with app.local_session() as c:
            assert c.card.skills[0].id == app.SKILL
            assert not c.card.capabilities.streaming
            task = await c.send(TICKET)
            output = app.task_output(task)
            assert output["state"] == "completed"
            assert task.id and task.context_id
            assert output["artifacts"][0]["data"][0] == await app.local_responder(TICKET)
            stored = await c.get(task.id)
            assert stored == task
            assert any(m.role == Role.ROLE_USER for m in stored.history)
            transport = c.transport
        assert transport.httpx_client.is_closed
    run(scenario())


def test_followup_preserves_task_context_and_history():
    async def scenario():
        async with app.local_session() as c:
            pending = await c.send({**TICKET, "issue": " "})
            assert pending.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
            assert not pending.artifacts
            task = await c.send(TICKET, task_id=pending.id, context_id=pending.context_id)
            assert (task.id, task.context_id) == (pending.id, pending.context_id)
            assert task.status.state == TaskState.TASK_STATE_COMPLETED
            assert sum(m.role == Role.ROLE_USER for m in task.history) == 2
    run(scenario())


def test_submission_limit_prevents_unbounded_followups():
    async def scenario():
        async with app.local_session() as c:
            ticket = {**TICKET, "issue": ""}
            task = await c.send(ticket)
            for _ in range(app.MAX_SUBMISSIONS - 1):
                task = await c.send(ticket, task_id=task.id, context_id=task.context_id)
                assert task.status.state == TaskState.TASK_STATE_INPUT_REQUIRED
            task = await c.send(TICKET, task_id=task.id, context_id=task.context_id)
            assert task.status.state == TaskState.TASK_STATE_REJECTED
            assert not task.artifacts
    run(scenario())


@pytest.mark.parametrize("ticket", [
    {**TICKET, "skill": "send_refund"}, {**TICKET, "category": "other"},
    {**TICKET, "issue": 42}, {**TICKET, "issue": "a" * 2001},
    {**TICKET, "extra": True}, {}, [], None,
])
def test_bad_requests_rejected_over_real_protocol(ticket):
    async def scenario():
        async with app.local_session() as c:
            task = await c.send(ticket)
            assert task.status.state == TaskState.TASK_STATE_REJECTED
            assert not task.artifacts
    run(scenario())


def test_malformed_json_rejected_over_protocol():
    async def scenario():
        async with app.local_session() as c:
            result = await c.transport.send_message(SendMessageRequest(message=Message(
                role=Role.ROLE_USER, message_id="malformed", parts=[Part(text="not json")],
            )))
            assert result.task.status.state == TaskState.TASK_STATE_REJECTED
    run(scenario())


@pytest.mark.parametrize("failure", ["exception", "invalid_report", "timeout"])
def test_specialist_failures_are_failed_tasks_without_artifacts(failure):
    async def respond(ticket):
        if failure == "exception":
            raise RuntimeError("private backend token")
        if failure == "timeout":
            raise asyncio.TimeoutError()
        return {"invented": "result"}
    async def scenario():
        async with app.local_session(respond) as c:
            task = await c.send(TICKET)
            assert task.status.state == TaskState.TASK_STATE_FAILED
            assert not task.artifacts
            assert "private backend token" not in json.dumps(app.task_output(task))
    run(scenario())


def test_missing_details_and_invalid_skill_do_not_call_responder():
    async def forbidden(ticket):
        pytest.fail("Responder should not have been called")
    async def scenario():
        async with app.local_session(forbidden) as c:
            await c.send({**TICKET, "issue": ""})
            await c.send({**TICKET, "skill": "unknown"})
    run(scenario())


def test_unknown_task_and_unsupported_cancel_are_protocol_errors():
    async def scenario():
        async with app.local_session() as c:
            with pytest.raises(TaskNotFoundError):
                await c.get("missing-task")
            pending = await c.send({**TICKET, "issue": ""})
            with pytest.raises(TaskNotCancelableError):
                await c.transport.cancel_task(CancelTaskRequest(id=pending.id))
    run(scenario())


def test_client_rejects_partial_resume_ids_and_oversize_messages():
    async def scenario():
        async with app.local_session() as c:
            with pytest.raises(ValueError, match="both"):
                await c.send(TICKET, task_id="a")
            with pytest.raises(ValueError, match="size"):
                await c.send({**TICKET, "issue": "x" * 4000})
    run(scenario())


def test_completed_task_cannot_be_resubmitted():
    async def scenario():
        async with app.local_session() as c:
            task = await c.send(TICKET)
            from a2a.utils.errors import UnsupportedOperationError
            with pytest.raises(UnsupportedOperationError):
                await c.send(TICKET, task_id=task.id, context_id=task.context_id)
    run(scenario())


@pytest.mark.parametrize("report", [None, [], {}, {"priority": "urgent", "summary": "a", "next_step": "b"},
    {"priority": "normal", "summary": " ", "next_step": "b"},
    {"priority": "normal", "summary": "a", "next_step": "b" * 1001}])
def test_invalid_report_validation(report):
    with pytest.raises(ValueError):
        app.validate_report(report)


@pytest.mark.parametrize("category", app.CATEGORIES)
def test_valid_categories_and_long_issue_produce_report(category):
    async def scenario():
        async with app.local_session() as c:
            task = await c.send({**TICKET, "category": category, "issue": "a" * 2000})
            report = app.task_output(task)["artifacts"][0]["data"][0]
            assert task.status.state == TaskState.TASK_STATE_COMPLETED
            assert len(report["summary"]) == 1000
            assert report["next_step"]
    run(scenario())


def test_parallel_tasks_do_not_mix_reports_or_ids():
    async def scenario():
        async with app.local_session() as c:
            tasks = await asyncio.gather(*[c.send({**TICKET, "issue": f"Issue {i}"}) for i in range(3)])
            assert len({task.id for task in tasks}) == 3
            assert len({task.context_id for task in tasks}) == 3
            for i, task in enumerate(tasks):
                assert app.task_output(await c.get(task.id))["artifacts"][0]["data"][0]["summary"] == f"Issue {i}"
    run(scenario())


def test_wrong_context_id_cannot_resume_task():
    async def scenario():
        from a2a.utils.errors import InvalidParamsError
        async with app.local_session() as c:
            task = await c.send({**TICKET, "issue": ""})
            with pytest.raises(InvalidParamsError):
                await c.send(TICKET, task_id=task.id, context_id="wrong-context")
            assert (await c.get(task.id)).status.state == TaskState.TASK_STATE_INPUT_REQUIRED
    run(scenario())


@pytest.mark.parametrize("field", ["summary", "next_step"])
@pytest.mark.parametrize("padding,leading", [
    pytest.param(1000, False, id="trailing-spaces"),
    pytest.param(1000, True, id="leading-spaces"),
    pytest.param(1000000, False, id="million-trailing-spaces"),
])
def test_report_length_counts_whitespace(field, padding, leading):
    text = " " * padding + "x" if leading else "x" + " " * padding
    report = {"priority": "normal", "summary": "Issue reported.", "next_step": "Request review.", field: text}
    with pytest.raises(ValueError, match="report text"):
        app.validate_report(report)


@pytest.mark.parametrize("field", ["summary", "next_step"])
def test_report_accepts_exact_raw_length_limit(field):
    text = " " + "x" * 998 + " "
    report = {"priority": "normal", "summary": "Issue reported.", "next_step": "Request review.", field: text}
    assert len(text) == 1000
    assert app.validate_report(report)[field] == text


@pytest.mark.parametrize("field", ["summary", "next_step"])
def test_padded_oversize_report_is_not_published(field):
    async def respond(ticket):
        return {"priority": "normal", "summary": "Issue reported.", "next_step": "Request review.",
                field: "x" + " " * 1000}
    async def scenario():
        async with app.local_session(respond) as c:
            task = await c.send(TICKET)
            assert task.status.state == TaskState.TASK_STATE_FAILED
            assert not task.artifacts
            stored = await c.get(task.id)
            assert stored.status.state == TaskState.TASK_STATE_FAILED
            assert not stored.artifacts
    run(scenario())
