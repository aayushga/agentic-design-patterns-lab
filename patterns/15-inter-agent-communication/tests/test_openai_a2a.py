"""Fake async model responses; real local A2A protocol; never live OpenAI."""
import asyncio
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

mod = importlib.import_module("patterns.15-inter-agent-communication.openai_version.openai_a2a")
app = importlib.import_module("patterns.15-inter-agent-communication.app")
TICKET = {"skill": app.SKILL, "category": "billing", "issue": "Invoice duplicated."}
REPORT = {"priority": "normal", "summary": "Possible duplicate invoice.", "next_step": "Request human billing review."}


def fake_sdk(monkeypatch, *, output=None, status="completed", error=None):
    requests, settings, lifecycle = [], [], []
    class FakeClient:
        def __init__(self, **kwargs):
            settings.append(kwargs)
            self.responses = SimpleNamespace(create=self.create)
        async def __aenter__(self):
            lifecycle.append("open")
            return self
        async def __aexit__(self, *args):
            lifecycle.append("closed")
        async def create(self, **kwargs):
            requests.append(kwargs)
            if error:
                raise error
            return SimpleNamespace(status=status, output_text=output)
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(AsyncOpenAI=FakeClient))
    monkeypatch.setenv("OPENAI_API_KEY", "offline-test-key")
    return requests, settings, lifecycle


def test_missing_key_before_import_or_protocol(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    async def scenario():
        async with mod.openai_session():
            pytest.fail("Must not open a session")
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        asyncio.run(scenario())


@pytest.mark.parametrize("explicit,environment,expected", [
    (None, None, mod.DEFAULT_MODEL), (None, "environment-model", "environment-model"),
    ("explicit-model", "environment-model", "explicit-model"),
])
def test_request_options_report_and_client_cleanup(monkeypatch, explicit, environment, expected):
    requests, settings, lifecycle = fake_sdk(monkeypatch, output=json.dumps(REPORT))
    if environment:
        monkeypatch.setenv("OPENAI_MODEL", environment)
    async def scenario():
        async with mod.openai_session(model=explicit) as c:
            pending = await c.send({**TICKET, "issue": ""})
            assert not requests
            task = await c.send(TICKET, task_id=pending.id, context_id=pending.context_id)
            assert app.task_output(task)["artifacts"][0]["data"][0] == REPORT
    asyncio.run(scenario())
    assert len(requests) == 1
    request = requests[0]
    assert request["model"] == expected
    assert request["max_output_tokens"] == 1500
    assert request["store"] is False
    assert request["reasoning"] == {"effort": "low"}
    assert request["text"]["format"]["strict"] is True
    assert json.loads(request["input"]) == TICKET
    assert "temperature" not in request
    assert settings == [{"api_key": "offline-test-key", "timeout": 30.0, "max_retries": 0}]
    assert lifecycle == ["open", "closed"]


@pytest.mark.parametrize("output,status,error", [
    ("not json", "completed", None), (None, "completed", None), ("", "completed", None),
    (json.dumps(REPORT), "failed", None), (json.dumps(REPORT), "incomplete", None),
    ('{"priority":"urgent","summary":"a","next_step":"b"}', "completed", None),
    (None, "completed", RuntimeError("private SDK error")),
])
def test_model_failures_become_safe_failed_tasks(monkeypatch, output, status, error):
    requests, _, lifecycle = fake_sdk(monkeypatch, output=output, status=status, error=error)
    async def scenario():
        async with mod.openai_session() as c:
            task = await c.send(TICKET)
            result = app.task_output(task)
            assert result["state"] == "failed"
            assert not result["artifacts"]
            assert "private SDK error" not in json.dumps(result)
    asyncio.run(scenario())
    assert len(requests) == 1
    assert lifecycle == ["open", "closed"]


def test_invalid_ticket_makes_no_model_request(monkeypatch):
    requests, _, lifecycle = fake_sdk(monkeypatch)
    async def scenario():
        async with mod.openai_session() as c:
            task = await c.send({**TICKET, "skill": "send_money"})
            assert app.task_output(task)["state"] == "rejected"
    asyncio.run(scenario())
    assert requests == []
    assert lifecycle == ["open", "closed"]
