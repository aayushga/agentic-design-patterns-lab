"""Tests for the Prompt Chaining pattern demo."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import (
    extract_key_themes,
    run_prompt_chain,
    summarize_text,
)


def test_summarize_text_truncates_when_needed() -> None:
    text = " ".join(["token"] * 40)
    summary = summarize_text(text, max_words=10)
    assert summary.endswith("...")
    assert len(summary.split()) == 10


def test_extract_key_themes_finds_expected_matches() -> None:
    summary = "We want faster workflow automation with better team collaboration."
    themes = extract_key_themes(summary)
    assert "automation" in themes
    assert "speed" in themes
    assert "collaboration" in themes


def test_run_prompt_chain_returns_structured_output() -> None:
    text = "Need reliable and efficient workflow quality improvements for operations."
    result = run_prompt_chain(text)
    assert result.summary
    assert isinstance(result.themes, list)
    assert "summary" in result.final_response
    assert "themes" in result.final_response
