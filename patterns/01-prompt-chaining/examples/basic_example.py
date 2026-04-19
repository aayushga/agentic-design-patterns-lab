"""Minimal runnable example of the Prompt Chaining pattern."""

from pathlib import Path
import sys

# Allow running example directly without packaging setup.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app import run_prompt_chain


if __name__ == "__main__":
    text = "We need a faster and more reliable process for handling repeated internal requests."
    result = run_prompt_chain(text)

    print("Summary:", result.summary)
    print("Themes:", result.themes)
    print("Final Response:", result.final_response)
