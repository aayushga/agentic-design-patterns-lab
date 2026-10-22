"""A small labeled evaluation set, honest metrics, local gates, and rolling alerts."""
from __future__ import annotations

import argparse
from collections import deque
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import time
from typing import Callable
from uuid import uuid4

ROUTES = ("billing", "support", "sales", "unknown")
ERROR_CODES = ("provider_error", "generation_not_completed", "invalid_output", "router_exception")


@dataclass(frozen=True)
class EvalCase:
    case_id: str
    query: str
    expected_route: str

    def __post_init__(self):
        if not isinstance(self.case_id, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,39}", self.case_id):
            raise ValueError("Invalid case ID")
        if not isinstance(self.query, str) or not 1 <= len(self.query) <= 500 or not self.query.strip():
            raise ValueError("Case queries need text of at most 500 raw characters")
        if self.expected_route not in ROUTES:
            raise ValueError("Invalid expected route")


@dataclass(frozen=True)
class Prediction:
    route: str | None
    error_code: str | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    abort_run: bool = False


@dataclass(frozen=True)
class Observation:
    case_id: str
    expected_route: str
    predicted_route: str | None
    status: str
    correct: bool
    latency_ms: float | None
    error_code: str | None
    input_tokens: int | None
    output_tokens: int | None


@dataclass(frozen=True)
class Report:
    schema_version: int
    run_id: str
    completed_at_utc: str
    variant: str
    model: str | None
    dataset_fingerprint: str
    timing_source: str
    observations: tuple[Observation, ...]
    metrics: dict


@dataclass(frozen=True)
class Thresholds:
    min_accuracy: float = 0.9
    max_error_rate: float = 0.1
    max_p95_ms: float = 200.0
    min_coverage: float = 1.0
    min_samples: int = 4

    def __post_init__(self):
        for value in (self.min_accuracy, self.max_error_rate, self.min_coverage):
            if type(value) not in (int, float) or not 0 <= value <= 1 or not math.isfinite(value):
                raise ValueError("Rate thresholds must be finite numbers from 0 to 1")
        if type(self.max_p95_ms) not in (int, float) or not 0 <= self.max_p95_ms <= 1000000:
            raise ValueError("Invalid latency threshold")
        if type(self.min_samples) is not int or not 1 <= self.min_samples <= 50:
            raise ValueError("min_samples must be from 1 to 50")


@dataclass(frozen=True)
class Gate:
    passed: bool
    reasons: tuple[str, ...]


Router = Callable[[str], Prediction]


def validate_cases(cases) -> tuple[EvalCase, ...]:
    if (not isinstance(cases, (tuple, list)) or not 1 <= len(cases) <= 50
            or any(not isinstance(c, EvalCase) for c in cases)):
        raise ValueError("Provide 1 to 50 EvalCase records")
    if len({c.case_id for c in cases}) != len(cases):
        raise ValueError("Case IDs must be unique")
    return tuple(cases)


def validate_limit(max_cases: int | None, count: int) -> int:
    if max_cases is None:
        return count
    if type(max_cases) is not int or not 0 <= max_cases <= 50:
        raise ValueError("max_cases must be an integer from 0 to 50")
    return min(max_cases, count)


def load_cases(path: str | Path | None = None) -> tuple[EvalCase, ...]:
    with Path(path or Path(__file__).with_name("cases.json")).open("rb") as handle:
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ValueError("Dataset exceeds 64 KiB")
    try:
        values = json.loads(raw)
        if not isinstance(values, list) or any(not isinstance(v, dict) or set(v) != {"case_id", "query", "expected_route"} for v in values):
            raise ValueError()
        return validate_cases([EvalCase(**value) for value in values])
    except (ValueError, TypeError, UnicodeError):
        raise ValueError("Invalid evaluation dataset") from None


def baseline_router(query: str) -> Prediction:
    text = query.casefold()
    if any(word in text for word in ("invoice", "charged", "charge", "billed", "refund")):
        route = "billing"
    elif any(word in text for word in ("password", "log in", "crash", "error")):
        route = "support"
    elif any(word in text for word in ("price", "pricing", "enterprise", "demo", "team plan")):
        route = "sales"
    else:
        route = "unknown"
    return Prediction(route)


def regressed_router(query: str) -> Prediction:
    """An intentionally flawed candidate, not an actual model regression."""
    text = query.casefold()
    if "crash" in text:
        raise RuntimeError("Simulated internal backend failure")
    if "billed" in text:
        return Prediction("sales")
    return baseline_router(query)


def summarize(observations: tuple[Observation, ...] | list[Observation]) -> dict:
    attempted = [o for o in observations if o.status != "not_run"]
    valid = [o for o in attempted if o.status == "ok"]
    correct = sum(o.correct for o in attempted)
    latencies = sorted(o.latency_ms for o in attempted)
    usage = [o for o in attempted if o.input_tokens is not None and o.output_tokens is not None]
    n, total = len(attempted), len(observations)
    per_route = {}
    for route in ROUTES:
        group = [o for o in attempted if o.expected_route == route]
        per_route[route] = {"attempted": len(group), "correct": sum(o.correct for o in group),
                            "accuracy": sum(o.correct for o in group) / len(group) if group else None}
    return {
        "case_count": total, "attempted_count": n, "valid_count": len(valid), "correct_count": correct,
        "coverage": n / total if total else 0.0,
        "accuracy": correct / n if n else None,
        "task_success_rate": correct / total if total else None,
        "schema_valid_rate": len(valid) / n if n else None,
        "error_rate": (n - len(valid)) / n if n else None,
        "mean_latency_ms": sum(latencies) / n if n else None,
        "p95_latency_ms": latencies[math.ceil(n * 0.95) - 1] if n else None,
        "usage_known_calls": len(usage),
        "known_input_tokens": sum(o.input_tokens for o in usage) if usage else None,
        "known_output_tokens": sum(o.output_tokens for o in usage) if usage else None,
        "usage_complete": len(usage) == n if n else None,
        "per_route": per_route,
    }


def evaluate(cases, router: Router = baseline_router, *, variant: str = "baseline",
             model: str | None = None, max_cases: int | None = None,
             clock: Callable[[], float] = time.perf_counter) -> Report:
    cases = validate_cases(cases)
    limit = validate_limit(max_cases, len(cases))
    if not isinstance(variant, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,40}", variant):
        raise ValueError("Invalid variant label")
    if model is not None and (not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9_.:/-]{1,100}", model)):
        raise ValueError("Invalid model label")
    observations = []
    aborted = False
    for index, case in enumerate(cases):
        if index >= limit or aborted:
            observations.append(Observation(case.case_id, case.expected_route, None, "not_run", False,
                                            None, "run_stopped" if aborted else "request_budget", None, None))
            continue
        start = clock()
        try:
            prediction = router(case.query)  # Never pass the label or identifying case ID.
        except Exception:
            prediction = Prediction(None, "router_exception")
        elapsed = (clock() - start) * 1000
        if not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("Evaluation clock must be finite and monotonic")
        code, route, input_tokens, output_tokens = "invalid_output", None, None, None
        if isinstance(prediction, Prediction):
            aborted = prediction.abort_run is True
            if (type(prediction.input_tokens) is int and 0 <= prediction.input_tokens <= 1000000000
                    and type(prediction.output_tokens) is int and 0 <= prediction.output_tokens <= 1000000000):
                input_tokens, output_tokens = prediction.input_tokens, prediction.output_tokens
            if prediction.error_code is not None:
                code = prediction.error_code if prediction.error_code in ERROR_CODES else "router_exception"
            elif prediction.route in ROUTES:
                code, route = None, prediction.route
        observations.append(Observation(case.case_id, case.expected_route, route, "ok" if code is None else "error",
                                        route == case.expected_route, elapsed, code, input_tokens, output_tokens))
    fingerprint = hashlib.sha256(json.dumps([asdict(c) for c in cases], sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return Report(1, uuid4().hex, datetime.now(timezone.utc).isoformat(timespec="seconds"), variant, model,
                  fingerprint, "perf_counter" if clock is time.perf_counter else "injected_clock",
                  tuple(observations), summarize(observations))


def _valid_gate_metrics(metrics: dict) -> bool:
    # Logs/caller-supplied metrics must not pass gates through NaN comparisons.
    try:
        n = metrics["attempted_count"]
        if type(n) is not int or not 0 <= n <= 50:
            return False
        coverage = metrics["coverage"]
        if type(coverage) not in (int, float) or not math.isfinite(coverage) or not 0 <= coverage <= 1:
            return False
        for name in ("accuracy", "error_rate", "p95_latency_ms"):
            value = metrics[name]
            if not n:
                if value is not None:
                    return False
            elif (type(value) not in (int, float) or not math.isfinite(value) or value < 0
                  or (name != "p95_latency_ms" and value > 1)):
                return False
        return True
    except (KeyError, TypeError, OverflowError):
        return False


def gate_metrics(metrics: dict, thresholds: Thresholds = Thresholds()) -> Gate:
    if not _valid_gate_metrics(metrics):
        return Gate(False, ("invalid_metrics",))
    reasons = []
    if metrics["attempted_count"] < thresholds.min_samples:
        reasons.append("insufficient_samples")
    if metrics["coverage"] < thresholds.min_coverage:
        reasons.append("incomplete_coverage")
    if metrics["accuracy"] is not None and metrics["accuracy"] < thresholds.min_accuracy:
        reasons.append("low_accuracy")
    if metrics["error_rate"] is not None and metrics["error_rate"] > thresholds.max_error_rate:
        reasons.append("high_error_rate")
    if metrics["p95_latency_ms"] is not None and metrics["p95_latency_ms"] > thresholds.max_p95_ms:
        reasons.append("high_p95_latency")
    return Gate(not reasons, tuple(reasons))


def quality_gate(report: Report, thresholds: Thresholds = Thresholds()) -> Gate:
    return gate_metrics(report.metrics, thresholds)


def compare_reports(baseline: Report, candidate: Report, *, max_accuracy_drop: float = 0.05) -> dict:
    if type(max_accuracy_drop) not in (int, float) or not 0 <= max_accuracy_drop <= 1:
        raise ValueError("max_accuracy_drop must be from 0 to 1")
    reasons = []
    if not _valid_gate_metrics(baseline.metrics) or not _valid_gate_metrics(candidate.metrics):
        return {"comparable": False, "accuracy_delta": None, "p95_latency_delta_ms": None, "reasons": ["invalid_metrics"]}
    if baseline.dataset_fingerprint != candidate.dataset_fingerprint:
        reasons.append("different_datasets")
    if baseline.metrics["coverage"] != 1 or candidate.metrics["coverage"] != 1:
        reasons.append("incomplete_coverage")
    if reasons:
        return {"comparable": False, "accuracy_delta": None, "p95_latency_delta_ms": None, "reasons": reasons}
    delta = candidate.metrics["accuracy"] - baseline.metrics["accuracy"]
    return {"comparable": True, "accuracy_delta": delta,
            "p95_latency_delta_ms": candidate.metrics["p95_latency_ms"] - baseline.metrics["p95_latency_ms"]
                if baseline.timing_source == candidate.timing_source else None,
            # With at most 50 cases, 1e-12 only absorbs floating-point boundary noise.
            "reasons": ["accuracy_regression"] if delta < -max_accuracy_drop
                and not math.isclose(delta, -max_accuracy_drop, rel_tol=0, abs_tol=1e-12) else []}


class RollingMonitor:
    """An in-process window for one stream/variant; it sends no notifications."""
    def __init__(self, window_size: int = 4, thresholds: Thresholds = Thresholds()):
        if type(window_size) is not int or not thresholds.min_samples <= window_size <= 50:
            raise ValueError("Window must fit min_samples and be at most 50")
        self.window = deque(maxlen=window_size)
        self.thresholds = thresholds

    def observe(self, observation: Observation) -> tuple[str, ...]:
        if not isinstance(observation, Observation):
            raise ValueError("Expected an Observation")
        if observation.status != "not_run":
            self.window.append(observation)
        if len(self.window) < self.thresholds.min_samples:
            return ()
        return gate_metrics(summarize(list(self.window)), self.thresholds).reasons


def append_jsonl(report: Report, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    metadata = {"schema_version": report.schema_version, "run_id": report.run_id,
                "completed_at_utc": report.completed_at_utc, "variant": report.variant,
                "model": report.model, "dataset_fingerprint": report.dataset_fingerprint,
                "timing_source": report.timing_source}
    lines = [{**metadata, "type": "case", "observation": asdict(o)} for o in report.observations]
    lines.append({**metadata, "type": "summary", "metrics": report.metrics, "gate": asdict(quality_gate(report))})
    with path.open("a", encoding="utf-8") as handle:
        handle.write("".join(json.dumps(line, allow_nan=False) + "\n" for line in lines))


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a fictional intent router and optionally append JSONL observations")
    parser.add_argument("--variant", choices=["baseline", "regressed"], default="baseline")
    parser.add_argument("--max-cases", type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fail-on-gate", action="store_true")
    args = parser.parse_args()
    router = baseline_router if args.variant == "baseline" else regressed_router
    report = evaluate(load_cases(), router, variant=args.variant, max_cases=args.max_cases)
    gate = quality_gate(report)
    print(json.dumps({"variant": report.variant, "timing_source": report.timing_source,
                      "metrics": report.metrics, "gate": asdict(gate)}, indent=2))
    if args.output:
        append_jsonl(report, args.output)
    if args.fail_on_gate and not gate.passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
