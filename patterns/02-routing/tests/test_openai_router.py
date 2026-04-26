"""Tests for optional OpenAI-backed router without live API calls."""

from pathlib import Path
import sys
import types

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from openai_version.openai_router import classify_intent_with_openai, route_with_openai


class _FakeResponse:
    def __init__(self, output_text: str) -> None:
        self.output_text = output_text


class _FakeResponsesAPI:
    def __init__(self, output_text: str) -> None:
        self._output_text = output_text

    def create(self, **_kwargs):
        return _FakeResponse(self._output_text)


class _FakeOpenAIClient:
    def __init__(self, output_text: str) -> None:
        self.responses = _FakeResponsesAPI(output_text)



def test_missing_api_key_raises_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)

    with pytest.raises(ValueError, match="Missing OPENAI_API_KEY"):
        classify_intent_with_openai("I need help")



def test_invalid_model_route_falls_back_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    fake_module = types.ModuleType("openai")
    fake_module.OpenAI = lambda api_key=None: _FakeOpenAIClient(
        '{"route":"engineering","confidence":"high","reason":"looks technical"}'
    )
    monkeypatch.setitem(sys.modules, "openai", fake_module)

    result = route_with_openai("Can someone look into this?")

    assert result.selected_route == "unknown"
    assert result.confidence == "low"
    assert "invalid route" in result.reason
    assert "could not confidently classify" in result.handler_response
