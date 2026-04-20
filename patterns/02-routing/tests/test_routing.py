"""Tests for the Routing pattern demo."""

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import route_input
from examples.advanced_example import run_advanced_router


def test_correct_route_selection() -> None:
    assert route_input("I need a refund for a charge").route == "billing"
    assert route_input("The app has a crash bug").route == "support"
    assert route_input("Can I see your pricing plans?").route == "sales"


def test_fallback_route_selection() -> None:
    result = route_input("What is your mission statement?")
    assert result.route == "unknown"
    assert "could not confidently classify" in result.response


def test_predictable_structured_output() -> None:
    result = run_advanced_router("I need help with a broken workflow")

    assert result.selected_route == "support"
    assert result.output["classification"]["route"] == "support"
    assert result.output["classification"]["confidence"] == "high"
    assert "explanation" in result.output
    assert "next_action" in result.output
