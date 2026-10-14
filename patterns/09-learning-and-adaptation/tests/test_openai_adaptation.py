"""Offline checks for policy-selected generation, free feedback, and failed attempts."""
import importlib
import json
import sys
from types import SimpleNamespace as NS

import pytest

module = importlib.import_module("patterns.09-learning-and-adaptation.openai_version.openai_adaptation")
app = importlib.import_module("patterns.09-learning-and-adaptation.app")


def reply_json(strategy="brief"):
    return json.dumps({"strategy": strategy, "acknowledgement": "Thanks for reporting the issue.",
                       "next_steps": ["Share the error message."] if strategy == "brief"
                       else ["Note the error message.", "Share it with your app version."]})


@pytest.fixture
def adaptation_sdk(monkeypatch):
    def install(*outputs, status="completed", error=None):
        pending = iter(outputs)
        requests, clients = [], []
        class Client:
            def __init__(self, **kwargs):
                self.state = {"options": kwargs, "closed": False}
                clients.append(self.state)
                self.responses = NS(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                self.state["closed"] = True
            def create(self, **kwargs):
                requests.append(kwargs)
                if error:
                    raise error
                return NS(status=status, output_text=next(pending))
        monkeypatch.setitem(sys.modules, "openai", NS(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return requests, clients
    return install


def test_feedback_changes_strategy_in_actual_next_request(adaptation_sdk):
    requests, clients = adaptation_sdk(reply_json(), reply_json("guided"), reply_json("guided"))
    policy, generator = app.AdaptivePolicy(), module.OpenAIResponder()
    first = module.run_openai_adaptation("Upload fails", "technical", policy, responder=generator)
    policy.feedback(first.episode_id, "not_helpful")
    assert len(requests) == 1  # Rating itself is a local operation.
    second = module.run_openai_adaptation("Upload fails", "technical", policy, responder=generator)
    policy.feedback(second.episode_id, "helpful")
    third = module.run_openai_adaptation("Follow-up", "technical", policy, responder=generator)
    assert [json.loads(item["input"])["strategy"] for item in requests] == ["brief", "guided", "guided"]
    assert first.response.count("\n- ") == 0 and third.response.count("\n- ") == 2
    assert second.scores_before == {"brief": 0.25, "guided": 0.5}
    assert all(r["store"] is False and r["reasoning"] == {"effort": "low"} for r in requests)
    assert all(r["model"] == "gpt-6-astra" and r["text"]["format"]["strict"] is True for r in requests)
    assert all(c["closed"] and c["options"]["max_retries"] == 0 and c["options"]["timeout"] == 30.0 for c in clients)
    assert generator.requests_used == 3


def test_feedback_and_reset_work_without_sdk_or_key(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    policy = app.AdaptivePolicy()
    answer = app.respond("Upload fails", "technical", policy)
    assert policy.feedback(answer.episode_id, "not_helpful").scores_after["brief"] == 0.25
    policy.reset("technical")
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}


@pytest.mark.parametrize("raw", ["not JSON", "[]", '{}',
    '{"strategy":"brief","acknowledgement":"Ack","next_steps":[]}',
    '{"strategy":"guided","acknowledgement":"Ack","next_steps":["one","two"]}',
    '{"strategy":"brief","acknowledgement":"Ack","next_steps":"step"}',
    '{"strategy":"brief","acknowledgement":"Ack","next_steps":["step"],"extra":1}'])
def test_invalid_response_never_records_episode_or_updates_scores(adaptation_sdk, raw):
    requests, clients = adaptation_sdk(raw)
    policy, generator = app.AdaptivePolicy(max_episodes=1), module.OpenAIResponder()
    with pytest.raises(ValueError):
        module.run_openai_adaptation("Upload fails", "technical", policy, responder=generator)
    assert generator.requests_used == len(requests) == 1 and clients[0]["closed"]
    assert policy.scores("technical") == {"brief": 0.5, "guided": 0.5}
    assert app.respond("Issue", "technical", policy).episode_id == 1


@pytest.mark.parametrize("status,text", [("incomplete", "partial"), ("failed", ""),
                                        ("completed", ""), ("completed", " "), ("completed", None)])
def test_unusable_response_fails_without_learning(adaptation_sdk, status, text):
    _, clients = adaptation_sdk(text, status=status)
    policy = app.AdaptivePolicy(max_episodes=1)
    with pytest.raises(RuntimeError):
        module.run_openai_adaptation("Issue", "technical", policy)
    assert clients[0]["closed"] and app.respond("Issue", "technical", policy).episode_id == 1


def test_api_error_consumes_attempt_but_not_episode(adaptation_sdk):
    requests, clients = adaptation_sdk(error=RuntimeError("API unavailable"))
    policy, generator = app.AdaptivePolicy(max_episodes=1), module.OpenAIResponder(max_requests=1)
    with pytest.raises(RuntimeError):
        module.run_openai_adaptation("Issue", "technical", policy, responder=generator)
    assert generator.requests_used == len(requests) == 1 and clients[0]["closed"]
    with pytest.raises(ValueError, match="request limit"):
        module.run_openai_adaptation("Issue", "technical", policy, responder=generator)
    assert len(requests) == 1 and app.respond("Issue", "technical", policy).episode_id == 1


def test_episode_limit_prevents_api_request(adaptation_sdk):
    requests, clients = adaptation_sdk(reply_json())
    policy, generator = app.AdaptivePolicy(max_episodes=1), module.OpenAIResponder()
    module.run_openai_adaptation("Issue", "technical", policy, responder=generator)
    with pytest.raises(ValueError, match="Episode limit"):
        module.run_openai_adaptation("Issue", "technical", policy, responder=generator)
    assert len(requests) == len(clients) == 1


def test_missing_key_before_client_creation_or_episode(adaptation_sdk, monkeypatch):
    requests, clients = adaptation_sdk()
    monkeypatch.delenv("OPENAI_API_KEY")
    policy, generator = app.AdaptivePolicy(), module.OpenAIResponder()
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_adaptation("Issue", "technical", policy, responder=generator)
    assert not requests and not clients and generator.requests_used == 0
    assert app.respond("Issue", "technical", policy).episode_id == 1


@pytest.mark.parametrize("query,context", [("", "technical"), (None, "technical"), ("Issue", "unknown")])
def test_invalid_inputs_before_client_creation(adaptation_sdk, query, context):
    requests, clients = adaptation_sdk()
    with pytest.raises(ValueError):
        module.run_openai_adaptation(query, context, app.AdaptivePolicy())
    assert not requests and not clients


@pytest.mark.parametrize("limit", [0, 21, True, 1.5])
def test_invalid_model_budget(limit):
    with pytest.raises(ValueError, match="max_requests"):
        module.OpenAIResponder(max_requests=limit)


@pytest.mark.parametrize("explicit,expected", [(None, "gpt-6.1-sol"), ("gpt-6-astra", "gpt-6-astra")])
def test_model_override_precedence(adaptation_sdk, monkeypatch, explicit, expected):
    requests, _ = adaptation_sdk(reply_json())
    monkeypatch.setenv("OPENAI_MODEL", "gpt-6.1-sol")
    module.run_openai_adaptation("Issue", "technical", app.AdaptivePolicy(), model=explicit)
    assert requests[0]["model"] == expected


def test_conflicting_model_and_shared_responder_rejected(adaptation_sdk):
    requests, _ = adaptation_sdk()
    with pytest.raises(ValueError, match="shared responder"):
        module.run_openai_adaptation("Issue", "technical", app.AdaptivePolicy(),
                                    responder=module.OpenAIResponder(), model="gpt-6-astra")
    assert not requests
