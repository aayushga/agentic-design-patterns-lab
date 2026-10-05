"""Offline coverage of the optional OpenAI chain and its step boundaries."""
from importlib import import_module
import pytest

chain = import_module("patterns.01-prompt-chaining.openai_version.openai_chain")


def test_missing_api_key():
    with pytest.raises(OSError, match="OPENAI_API_KEY"):
        chain.run_prompt_chain("Support ticket")


def test_chain_passes_each_output_to_next_step(fake_openai):
    _, requests = fake_openai("Short summary", '["quality", "speed"]',
                              '{"recommended_next_step":"Review workflow","input_length":999}')
    result = chain.run_prompt_chain("Original input")
    assert result.summary == "Short summary"
    assert result.themes == ["quality", "speed"]
    assert result.final_response == {
        "input_length": len("Original input"), "summary": "Short summary",
        "themes": ["quality", "speed"], "recommended_next_step": "Review workflow",
    }
    assert len(requests) == 3
    assert "Short summary" in requests[1]["input"][1]["content"]
    assert "quality" in requests[2]["input"][1]["content"]
    for request in requests:
        assert request["model"] == "gpt-6-astra"
        assert request["reasoning"] == {"effort": "low"}
        assert "temperature" not in request


@pytest.mark.parametrize("raw", ['not JSON', 'null', '{}', '[]', '[1]', '[" "]'])
def test_invalid_themes_use_general_fallback(fake_openai, raw):
    client, _ = fake_openai(raw)
    assert chain.extract_key_themes(client, "summary") == ["general"]


@pytest.mark.parametrize("raw", ['not JSON', 'null', '[]', '{}', '{"recommended_next_step":null}'])
def test_invalid_final_response_preserves_known_fields(fake_openai, raw):
    client, _ = fake_openai(raw)
    result = chain.generate_structured_response(client, "input", "summary", ["quality"])
    assert result == {
        "input_length": 5, "summary": "summary", "themes": ["quality"],
        "recommended_next_step": "Review the summary and themes before taking action.",
    }


@pytest.mark.parametrize("content,status", [(None, "completed"), ("", "completed"), (" ", "completed"), ("partial", "incomplete")])
def test_missing_or_incomplete_step_stops_chain(fake_openai, content, status):
    _, requests = fake_openai(content, status=status)
    with pytest.raises(RuntimeError):
        chain.run_prompt_chain("input")
    assert len(requests) == 1


@pytest.mark.parametrize("env,explicit,expected", [
    ("env-model", None, "env-model"), ("env-model", "explicit-model", "explicit-model"),
    (" ", None, "gpt-6-astra"),
])
def test_model_selection_for_all_steps(fake_openai, monkeypatch, env, explicit, expected):
    _, requests = fake_openai("summary", '["quality"]', '{"recommended_next_step":"Review"}')
    monkeypatch.setenv("OPENAI_MODEL", env)
    chain.run_prompt_chain("input", model=explicit)
    assert [request["model"] for request in requests] == [expected] * 3


def test_blank_input_does_not_call_api(fake_openai):
    _, requests = fake_openai()
    with pytest.raises(ValueError, match="non-empty"):
        chain.run_prompt_chain(" ")
    assert requests == []


def test_api_failure_stops_chain(fake_openai):
    _, requests = fake_openai(error=RuntimeError("simulated API failure"))
    with pytest.raises(RuntimeError, match="simulated API failure"):
        chain.run_prompt_chain("input")
    assert len(requests) == 1


def test_cli_configuration_error():
    with pytest.raises(SystemExit, match="OPENAI_API_KEY"):
        chain.main()
