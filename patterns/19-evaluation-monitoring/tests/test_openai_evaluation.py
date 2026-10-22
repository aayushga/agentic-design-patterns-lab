"""Fake SDK only: no key, SDK installation, or live API access required."""
import importlib
import json
import sys
from types import SimpleNamespace

import pytest

app = importlib.import_module("patterns.19-evaluation-monitoring.app")
module = importlib.import_module("patterns.19-evaluation-monitoring.openai_version.openai_evaluation")


def response(route="billing", *, raw=None, status="completed", usage=True):
    return SimpleNamespace(output_text=json.dumps({"route": route}) if raw is None else raw,
                           status=status, usage=SimpleNamespace(input_tokens=11, output_tokens=7) if usage else None)


@pytest.fixture
def sdk(monkeypatch):
    def install(*outputs):
        state = {"requests": [], "closed": False}
        remaining = iter(outputs)
        class Client:
            def __init__(self, **kwargs):
                state["options"] = kwargs
                self.responses = SimpleNamespace(create=self.create)
            def __enter__(self):
                return self
            def __exit__(self, *args):
                state["closed"] = True
            def create(self, **kwargs):
                state["requests"].append(kwargs)
                output = next(remaining)
                if isinstance(output, Exception):
                    raise output
                return output
        monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=Client))
        monkeypatch.setenv("OPENAI_API_KEY", "offline-placeholder")
        return state
    return install


def test_key_missing_before_sdk_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        module.run_openai_evaluation()


def test_zero_budget_requires_neither_key_nor_sdk(monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    report = module.run_openai_evaluation(max_cases=0)
    assert report.metrics["attempted_count"] == 0
    assert not app.quality_gate(report).passed


def test_default_budget_request_contract_and_usage(sdk):
    state = sdk(response(), response(), response("support"))
    report = module.run_openai_evaluation()
    assert len(state["requests"]) == 3
    assert state["closed"]
    assert state["options"] == {"api_key": "offline-placeholder", "timeout": 30.0, "max_retries": 0}
    for request, case in zip(state["requests"], app.load_cases()):
        assert json.loads(request["input"]) == {"query": case.query}
        assert case.case_id not in json.dumps(request)
        assert "expected_route" not in json.dumps(request)
        assert request["model"] == "gpt-6-astra"
        assert request["reasoning"] == {"effort": "low"}
        assert request["max_output_tokens"] == 1000
        assert request["store"] is False
        assert request["text"]["format"]["strict"] is True
    assert report.metrics["known_input_tokens"] == 33
    assert report.metrics["known_output_tokens"] == 21
    assert report.metrics["usage_complete"] is True
    assert report.metrics["coverage"] == .375
    assert report.metrics["accuracy"] == 1
    assert not app.quality_gate(report).passed


@pytest.mark.parametrize("explicit,expected", [(None,"environment-model"),("chosen-model","chosen-model")])
def test_model_precedence(monkeypatch,sdk,explicit,expected):
    monkeypatch.setenv("OPENAI_MODEL", "environment-model")
    state = sdk(response())
    assert module.run_openai_evaluation(model=explicit,max_cases=1).model == expected
    assert state["requests"][0]["model"] == expected


@pytest.mark.parametrize("raw", ['{"route":"invalid"}', '{}', '{"route":"billing","extra":1}',
    '{"route":["billing"]}', 'null', 'not JSON', '', 'x'*1001])
def test_invalid_outputs_count_as_errors_and_preserve_usage(sdk,raw):
    state = sdk(response(raw=raw),response())
    report = module.run_openai_evaluation(max_cases=2)
    assert report.observations[0].error_code == "invalid_output"
    assert report.observations[0].predicted_route is None
    assert report.metrics["known_output_tokens"] == 14
    assert report.metrics["accuracy"] == .5
    assert len(state["requests"]) == 2


def test_incomplete_generation_usage_is_counted(sdk):
    sdk(response(status="incomplete"))
    report = module.run_openai_evaluation(max_cases=1)
    assert report.observations[0].error_code == "generation_not_completed"
    assert report.metrics["known_output_tokens"] == 7


def test_provider_failure_stops_without_retries_or_raw_exception(sdk):
    state = sdk(response(), RuntimeError("SECRET_PROVIDER_ERROR"))
    report = module.run_openai_evaluation(max_cases=8)
    assert len(state["requests"]) == 2 and state["closed"]
    assert report.metrics["attempted_count"] == 2
    assert report.metrics["coverage"] == .25
    assert report.metrics["known_input_tokens"] == 11
    assert report.metrics["usage_complete"] is False
    assert report.observations[1].error_code == "provider_error"
    assert all(o.status == "not_run" for o in report.observations[2:])
    assert "SECRET_PROVIDER_ERROR" not in repr(report)


def test_full_dataset_budget_is_clamped(sdk):
    state = sdk(*(response(case.expected_route) for case in app.load_cases()))
    report = module.run_openai_evaluation(max_cases=50)
    assert len(state["requests"]) == 8
    assert report.metrics["coverage"] == 1
    assert app.quality_gate(report).passed


def test_usage_unknown_when_provider_omits_usage(sdk):
    sdk(response(usage=False))
    report = module.run_openai_evaluation(max_cases=1)
    assert report.metrics["known_output_tokens"] is None
    assert report.metrics["usage_complete"] is False


@pytest.mark.parametrize("max_cases", [-1, 51, True, 1.5, None])
def test_bad_budget_validated_before_key_or_sdk(max_cases,monkeypatch):
    monkeypatch.setitem(sys.modules, "openai", None)
    with pytest.raises(ValueError, match="max_cases"):
        module.run_openai_evaluation(max_cases=max_cases)
