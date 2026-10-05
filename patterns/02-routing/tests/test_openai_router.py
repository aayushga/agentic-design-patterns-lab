"""Router contract and failure cases; no real OpenAI API calls."""
from dataclasses import asdict
from importlib import import_module
import json

import pytest

router = import_module("patterns.02-routing.openai_version.openai_router")


def test_missing_api_key_raises_clear_error():
    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        router.classify_intent_with_openai("I need help")


@pytest.mark.parametrize("route,handler", [
    ("billing", "Billing team"), ("support", "Support team"),
    ("sales", "Sales team"), ("unknown", "General desk"),
])
def test_dispatch_preserves_output_contract(fake_openai, route, handler):
    _, requests = fake_openai(json.dumps({"route": route, "confidence": "high", "reason": "Intent match"}))
    result = router.route_with_openai("Original request")
    assert result.selected_route == route
    assert result.original_query == "Original request"
    assert handler in result.handler_response
    assert set(asdict(result)) == {"original_query", "selected_route", "confidence", "reason", "handler_response"}
    assert result.confidence == ("low" if route == "unknown" else "high")
    assert requests[0]["model"] == "gpt-6-astra"
    assert requests[0]["reasoning"] == {"effort": "low"}
    assert "temperature" not in requests[0]
    assert requests[0]["text"]["format"]["type"] == "json_schema"


@pytest.mark.parametrize("payload", ["", "not JSON", "null", "[]", "42", "{}", None,
    '{"route": "engineering", "confidence": "high", "reason": "technical"}',
    '{"route": [], "confidence": "high", "reason": "technical"}',
    '{"route": "sales", "confidence": "high", "reason": null}',
])
def test_unusable_model_output_falls_back(fake_openai, payload):
    fake_openai(payload)
    result = router.route_with_openai("Can someone help?")
    assert result.selected_route == "unknown"
    assert result.confidence == "low"
    assert result.reason
    assert "could not confidently classify" in result.handler_response


def test_normalization_and_invalid_confidence(fake_openai):
    fake_openai('{"route":" SUPPORT ","confidence": [],"reason":" needs help "}')
    result = router.route_with_openai("Help")
    assert (result.selected_route, result.confidence, result.reason) == ("support", "low", "needs help")


def test_incomplete_response_falls_back(fake_openai):
    fake_openai('{"route":"sales","confidence":"high","reason":"buy"}', status="incomplete")
    assert router.route_with_openai("buy").selected_route == "unknown"


@pytest.mark.parametrize("env,explicit,expected", [
    ("custom-env-model", None, "custom-env-model"),
    ("custom-env-model", "explicit-model", "explicit-model"),
    ("  ", None, "gpt-6-astra"),
])
def test_model_selection(fake_openai, monkeypatch, env, explicit, expected):
    _, requests = fake_openai('{"route":"sales","confidence":"high","reason":"buy"}')
    monkeypatch.setenv("OPENAI_MODEL", env)
    router.route_with_openai("buy", model=explicit)
    assert requests[0]["model"] == expected


def test_blank_input_does_not_call_api(fake_openai):
    _, requests = fake_openai()
    with pytest.raises(ValueError, match="non-empty"):
        router.route_with_openai("  ")
    assert requests == []


def test_api_failure_is_not_misrepresented_as_classification(fake_openai):
    fake_openai(error=RuntimeError("offline simulated API failure"))
    with pytest.raises(RuntimeError, match="simulated API failure"):
        router.route_with_openai("help")


def test_cli_configuration_error(monkeypatch):
    monkeypatch.setattr("builtins.input", lambda _: "help")
    with pytest.raises(SystemExit, match="Missing OPENAI_API_KEY"):
        router.main()
