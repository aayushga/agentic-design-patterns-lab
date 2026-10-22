"""Model proposals, deterministic arithmetic checks, and one bounded correction."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

if __package__:
    from ..app import MAX_EXPRESSION_CHARS, Puzzle, ReasoningResult, verify_expression
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import MAX_EXPRESSION_CHARS, Puzzle, ReasoningResult, verify_expression

DEFAULT_MODEL = "gpt-6-astra"
CANDIDATE_FORMAT = {
    "type": "json_schema", "name": "arithmetic_candidates", "strict": True,
    "schema": {
        "type": "object", "properties": {
            "candidates": {"type": "array", "maxItems": 3, "items": {
                "type": "string", "maxLength": MAX_EXPRESSION_CHARS,
            }},
        }, "required": ["candidates"], "additionalProperties": False,
    },
}
INSTRUCTIONS = (
    "Solve the supplied arithmetic puzzle. Return up to three candidate expressions, "
    "or an empty list if you cannot find a candidate. Each must use all four supplied "
    "integers exactly once, with only binary +, -, *, / and parentheses, to reach "
    "the target exactly. Fractional intermediate results are allowed. Do not use "
    "concatenation, unary operators, functions, powers, or extra numbers. Return "
    "expressions only, no reasoning narrative. Any supplied feedback is from a "
    "deterministic checker; revise rejected expressions using those observations."
)


def parse_candidates(raw: object) -> list[str]:
    if not isinstance(raw, str) or not 1 <= len(raw) <= 2000:
        raise ValueError("Invalid candidate response size")
    value = json.loads(raw)
    if not isinstance(value, dict) or set(value) != {"candidates"}:
        raise ValueError("Invalid candidate response fields")
    candidates = value["candidates"]
    if not isinstance(candidates, list) or len(candidates) > 3:
        raise ValueError("Invalid candidate count")
    if any(not isinstance(c, str) or not 1 <= len(c) <= MAX_EXPRESSION_CHARS for c in candidates):
        raise ValueError("Invalid candidate expression size")
    return candidates


def run_openai_reasoning(puzzle: Puzzle = Puzzle(), *, model: str | None = None,
                         max_attempts: int = 2) -> ReasoningResult:
    if not isinstance(puzzle, Puzzle):
        raise ValueError("puzzle must be a Puzzle")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 2:
        raise ValueError("max_attempts must be 1 or 2")
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise ValueError("Missing OPENAI_API_KEY. Export it before running optional model proposals.")
    selected_model = model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    from openai import OpenAI

    checks = []
    with OpenAI(api_key=key, timeout=30.0, max_retries=0) as client:
        for attempt in range(1, max_attempts + 1):
            def finish(status, solution, reason):
                return ReasoningResult(puzzle, "model_propose_verify", status, solution,
                                       tuple(checks), 0, attempt, reason)
            try:
                response = client.responses.create(
                    model=selected_model, reasoning={"effort": "medium"}, max_output_tokens=2000,
                    store=False, instructions=INSTRUCTIONS,
                    input=json.dumps({"puzzle": asdict(puzzle), "checked_proposals": [asdict(c) for c in checks]}),
                    text={"format": CANDIDATE_FORMAT},
                )
            except Exception:
                return finish("failed", None, "model_request_failed")
            if response.status != "completed":
                return finish("failed", None, "model_not_completed")
            try:
                candidates = parse_candidates(response.output_text)
            except (ValueError, TypeError):
                return finish("failed", None, "invalid_model_output")
            if not candidates:
                return finish("unverified", None, "model_abstained")
            batch = [verify_expression(puzzle, expression) for expression in candidates]
            checks.extend(batch)
            accepted = next((c for c in batch if c.valid), None)
            if accepted:
                return finish("solved", accepted.expression, "verified_candidate")
        return finish("unverified", None, "model_budget")


def main() -> None:
    parser = argparse.ArgumentParser(description="Propose and exactly verify arithmetic puzzle answers")
    parser.add_argument("--numbers", nargs=4, type=int, default=[3, 3, 8, 8])
    parser.add_argument("--target", type=int, default=24)
    parser.add_argument("--max-attempts", type=int, default=2)
    args = parser.parse_args()
    try:
        puzzle = Puzzle(tuple(args.numbers), args.target)
        print("Optional demo: at most two billable model attempts; all arithmetic checks are local.")
        print(json.dumps(asdict(run_openai_reasoning(puzzle, max_attempts=args.max_attempts)), indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    except Exception:
        raise SystemExit("Could not start the model proposer. Check SDK installation and configuration.") from None


if __name__ == "__main__":
    main()
