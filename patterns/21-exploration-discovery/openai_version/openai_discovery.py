"""An optional model proposes the next experiment; only the host creates evidence."""
from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import sys

if __package__:
    from ..app import Proposal, ProposerConfigurationError, Report, explore, validate_budgets
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import Proposal, ProposerConfigurationError, Report, explore, validate_budgets

DEFAULT_MODEL = "gpt-6-astra"
INSTRUCTIONS = (
    "Choose one offered experiment ID to learn about the fictional pipeline and seek the latency target. "
    "Balance exploring unseen setting values with testing combinations near promising observations. "
    "Use only the recorded evidence; unknown outcomes have not been measured. "
    "Return only config_id. Do not invent measurements, claim success, generate code, or execute actions."
)


class ModelProposer:
    def __init__(self, model, max_model_requests):
        self.model, self.limit, self.attempts, self.stopped = model, max_model_requests, 0, False

    def __call__(self, offered, trials, target):
        if not self.limit:
            return Proposal(None, "model_disabled")
        if self.stopped:
            return Proposal(None, "model_stopped")
        if self.attempts >= self.limit:
            return Proposal(None, "model_budget_exhausted")
        key = os.getenv("OPENAI_API_KEY", "").strip()
        if not key:
            raise ProposerConfigurationError("Missing OPENAI_API_KEY. Export it before requesting an optional model proposal.")
        try:
            from openai import OpenAI
        except ImportError:
            raise ProposerConfigurationError("Install openai_version/requirements.txt to enable model proposals.") from None
        ids = [c.configuration.config_id for c in offered]
        output_format = {"type": "json_schema", "name": "next_experiment", "strict": True,
            "schema": {"type": "object", "properties": {"config_id": {"type": "string", "enum": ids}},
                       "required": ["config_id"], "additionalProperties": False}}
        payload = {"target_latency_ms": target,
            "candidates": [{"config_id": c.configuration.config_id, "configuration": asdict(c.configuration),
                "cost_units": c.configuration.cost_units, "novel_values": c.novel_values,
                "best_parent_latency_ms": c.best_parent_latency_ms} for c in offered],
            "evidence": [{"config_id": t.config_id, "configuration": asdict(t.configuration), "status": t.status,
                          "latency_ms": t.latency_ms, "error_code": t.error_code} for t in trials]}
        self.attempts += 1
        try:
            with OpenAI(api_key=key, timeout=30.0, max_retries=0) as client:
                response = client.responses.create(model=self.model, reasoning={"effort": "low"},
                    max_output_tokens=1000, store=False, instructions=INSTRUCTIONS,
                    input=json.dumps(payload), text={"format": output_format})
        except Exception:
            self.stopped = True
            return Proposal(None, "provider_error")
        if response.status != "completed":
            self.stopped = True
            return Proposal(None, "generation_not_completed")
        try:
            raw = response.output_text
            if not isinstance(raw, str) or not 1 <= len(raw) <= 256:
                raise ValueError()
            value = json.loads(raw)
            if (not isinstance(value, dict) or set(value) != {"config_id"}
                    or not isinstance(value["config_id"], str) or value["config_id"] not in ids):
                raise ValueError()
        except (ValueError, TypeError):
            self.stopped = True
            return Proposal(None, "invalid_output")
        return Proposal(value["config_id"])


@dataclass(frozen=True)
class ModelResult:
    model: str
    model_attempts: int
    report: Report


def run_openai_discovery(*, model: str | None = None, max_model_requests=3,
                         max_experiments=6, cost_budget=8, target_latency_ms=50) -> ModelResult:
    validate_budgets(max_experiments, cost_budget, target_latency_ms)
    if type(max_model_requests) is not int or not 0 <= max_model_requests <= 3:
        raise ValueError("max_model_requests must be an integer from 0 to 3")
    selected = model or os.getenv("OPENAI_MODEL", "").strip() or DEFAULT_MODEL
    if not isinstance(selected, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", selected):
        raise ValueError("Invalid model label")
    proposer = ModelProposer(selected, max_model_requests)
    report = explore(max_experiments=max_experiments, cost_budget=cost_budget,
                     target_latency_ms=target_latency_ms, proposer=proposer)
    return ModelResult(selected, proposer.attempts, report)


def main() -> None:
    parser = argparse.ArgumentParser(description="Bounded model proposals with free host-side simulated experiments")
    parser.add_argument("--max-model-requests", type=int, default=3)
    parser.add_argument("--max-experiments", type=int, default=6)
    parser.add_argument("--cost-budget", type=int, default=8)
    parser.add_argument("--target-ms", type=int, default=50)
    args = parser.parse_args()
    try:
        result = run_openai_discovery(max_model_requests=args.max_model_requests,
            max_experiments=args.max_experiments, cost_budget=args.cost_budget, target_latency_ms=args.target_ms)
        print(json.dumps(asdict(result), indent=2))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
