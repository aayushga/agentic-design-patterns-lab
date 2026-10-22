"""Discover behavior through bounded experiments in a fictional, finite lab."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True)
class Configuration:
    cache: bool = False
    batch_size: int = 1
    compression: bool = False

    def __post_init__(self):
        if type(self.cache) is not bool or type(self.compression) is not bool:
            raise ValueError("Cache and compression must be booleans")
        if type(self.batch_size) is not int or self.batch_size not in (1, 4):
            raise ValueError("Batch size must be 1 or 4")

    @property
    def config_id(self) -> str:
        return f"cfg-{int(self.cache) + 2 * (self.batch_size == 4) + 4 * int(self.compression):02d}"

    @property
    def cost_units(self) -> int:
        return 2 if self.batch_size == 4 else 1


CATALOG = tuple(Configuration(bool(i & 1), 4 if i & 2 else 1, bool(i & 4)) for i in range(8))


@dataclass(frozen=True)
class Measurement:
    latency_ms: int


@dataclass(frozen=True)
class Observation:
    configuration: Configuration
    latency_ms: int


@dataclass(frozen=True)
class Candidate:
    configuration: Configuration
    novel_values: int
    best_parent_latency_ms: int | None


@dataclass(frozen=True)
class Proposal:
    config_id: str | None
    error_code: str | None = None


class ProposerConfigurationError(ValueError):
    """A missing credential/dependency is a setup error, not experimental evidence."""


@dataclass(frozen=True)
class Trial:
    step: int
    configuration: Configuration
    config_id: str
    cost_units: int
    selection_source: str
    selection_reason: str
    status: str
    latency_ms: int | None
    error_code: str | None
    improved_best: bool


@dataclass(frozen=True)
class Report:
    stop_reason: str
    target_latency_ms: int
    target_met: bool
    best_config_id: str | None
    best_latency_ms: int | None
    trials: tuple[Trial, ...]
    spent_cost_units: int
    remaining_cost_units: int
    attempted_coverage: float
    successful_observations: int
    failed_config_ids: tuple[str, ...]
    untried_config_ids: tuple[str, ...]
    frontier_ids: tuple[str, ...]


Proposer = Callable[[tuple[Candidate, ...], tuple[Trial, ...], int], Proposal]
Experiment = Callable[[Configuration], Measurement]


def validate_budgets(max_experiments, cost_budget, target_latency_ms):
    for value, name, low, high in ((max_experiments, "max_experiments", 0, 8),
                                   (cost_budget, "cost_budget", 0, 16),
                                   (target_latency_ms, "target_latency_ms", 1, 10000)):
        if type(value) is not int or not low <= value <= high:
            raise ValueError(f"{name} must be an integer from {low} to {high}")


def neighbors(config: Configuration) -> tuple[Configuration, ...]:
    return tuple(sorted((Configuration(not config.cache, config.batch_size, config.compression),
                         Configuration(config.cache, 1 if config.batch_size == 4 else 4, config.compression),
                         Configuration(config.cache, config.batch_size, not config.compression)),
                        key=lambda c: c.config_id))


def feature_values(config: Configuration) -> frozenset:
    return frozenset((("cache", config.cache), ("batch_size", config.batch_size), ("compression", config.compression)))


def rank_frontier(frontier, observations, remaining_cost) -> tuple[Candidate, ...]:
    """Only successful observations inform novelty and promising-parent scores."""
    seen = set().union(*(feature_values(o.configuration) for o in observations)) if observations else set()
    ranked = []
    for config in frontier:
        if config.cost_units > remaining_cost:
            continue
        parent_times = [o.latency_ms for o in observations if config in neighbors(o.configuration)]
        ranked.append(Candidate(config, len(feature_values(config) - seen), min(parent_times) if parent_times else None))
    return tuple(sorted(ranked, key=lambda c: (-c.novel_values,
                        c.best_parent_latency_ms if c.best_parent_latency_ms is not None else float("inf"),
                        c.configuration.config_id)))


def simulate_experiment(config: Configuration) -> Measurement:
    """Fictional lab truth. Selection policies never receive this outcome table."""
    # Combined settings must be measured; isolated changes do not establish their outcome.
    latencies = (120, 80, 90, 45, 110, 70, 85, None)
    result = latencies[CATALOG.index(config)]
    if result is None:
        raise RuntimeError("The fictional all-enabled configuration is unsupported")
    return Measurement(result)


def explore(*, max_experiments=6, cost_budget=8, target_latency_ms=50,
            proposer: Proposer | None = None, experiment: Experiment = simulate_experiment) -> Report:
    validate_budgets(max_experiments, cost_budget, target_latency_ms)
    frontier = {CATALOG[0].config_id: CATALOG[0]}
    attempted, observations, trials = set(), [], []
    remaining = cost_budget
    best = None
    fallback_codes = ("provider_error", "generation_not_completed", "invalid_output", "invalid_proposal", "proposer_error")
    local_codes = ("model_disabled", "model_budget_exhausted", "model_stopped")
    while True:
        if best is not None and best.latency_ms <= target_latency_ms:
            stop = "target_met"
            break
        if not frontier:
            stop = "frontier_exhausted"
            break
        if len(trials) >= max_experiments:
            stop = "experiment_limit"
            break
        offered = rank_frontier(tuple(frontier.values()), tuple(observations), remaining)
        if not offered:
            stop = "cost_limit"
            break
        selected = offered[0].configuration
        source = "rules"
        reason = "only_candidate" if len(offered) == 1 else "novelty_then_parent"
        if proposer is not None and len(offered) > 1:
            try:
                proposal = proposer(offered, tuple(trials), target_latency_ms)
            except ProposerConfigurationError:
                raise
            except Exception:
                proposal = Proposal(None, "proposer_error")
            offered_by_id = {c.configuration.config_id: c.configuration for c in offered}
            if (isinstance(proposal, Proposal) and proposal.error_code is None
                    and isinstance(proposal.config_id, str) and proposal.config_id in offered_by_id):
                selected = offered_by_id[proposal.config_id]
                source, reason = "proposal", "validated_proposal"
            else:
                code = proposal.error_code if isinstance(proposal, Proposal) else None
                reason = code if isinstance(code, str) and code in fallback_codes + local_codes else "invalid_proposal"
                source = "rules" if reason in local_codes else "rules_fallback"
        # Reserve both budgets before execution, including for failed/invalid experiments.
        del frontier[selected.config_id]
        attempted.add(selected.config_id)
        remaining -= selected.cost_units
        latency, error = None, None
        try:
            measured = experiment(selected)
            if (not isinstance(measured, Measurement) or type(measured.latency_ms) is not int
                    or not 1 <= measured.latency_ms <= 10000):
                error = "invalid_measurement"
            else:
                latency = measured.latency_ms
        except Exception:
            error = "experiment_error"
        improved = latency is not None and (best is None or latency < best.latency_ms)
        if latency is not None:
            observation = Observation(selected, latency)
            observations.append(observation)
            if improved:
                best = observation
            for neighbor in neighbors(selected):
                if neighbor.config_id not in attempted:
                    frontier[neighbor.config_id] = neighbor
        trials.append(Trial(len(trials) + 1, selected, selected.config_id, selected.cost_units,
                            source, reason, "observed" if latency is not None else "failed",
                            latency, error, improved))
    return Report(stop, target_latency_ms, best is not None and best.latency_ms <= target_latency_ms,
                  best.configuration.config_id if best else None, best.latency_ms if best else None,
                  tuple(trials), cost_budget - remaining, remaining, len(attempted) / len(CATALOG),
                  len(observations), tuple(t.config_id for t in trials if t.status == "failed"),
                  tuple(c.config_id for c in CATALOG if c.config_id not in attempted), tuple(sorted(frontier)))


def print_report(report: Report) -> None:
    for trial in report.trials:
        result = f"{trial.latency_ms}ms" if trial.latency_ms is not None else f"FAILED ({trial.error_code})"
        print(f"{trial.step}. {trial.config_id}: cache={trial.configuration.cache}, batch={trial.configuration.batch_size}, "
              f"compression={trial.configuration.compression} -> {result}; cost={trial.cost_units}; "
              f"choice={trial.selection_source}/{trial.selection_reason}")
    print(f"Stop: {report.stop_reason}; target met: {report.target_met}")
    print(f"Best observed: {report.best_config_id} at {report.best_latency_ms}ms" if report.best_config_id else "Best observed: none")
    print(f"Spent: {report.spent_cost_units} simulated cost units; remaining: {report.remaining_cost_units}")
    print(f"Attempted coverage: {report.attempted_coverage:.1%}; valid observations: {report.successful_observations}")
    print("Untried:", ", ".join(report.untried_config_ids) or "none")
    print("Failed:", ", ".join(report.failed_config_ids) or "none")


def main() -> None:
    parser = argparse.ArgumentParser(description="Explore fictional pipeline settings through bounded local experiments")
    parser.add_argument("--max-experiments", type=int, default=6)
    parser.add_argument("--cost-budget", type=int, default=8)
    parser.add_argument("--target-ms", type=int, default=50)
    args = parser.parse_args()
    try:
        print("Free fictional lab: latencies and cost units are simulated; no live tuning or API calls.")
        print_report(explore(max_experiments=args.max_experiments, cost_budget=args.cost_budget,
                             target_latency_ms=args.target_ms))
    except ValueError as exc:
        raise SystemExit(str(exc)) from None


if __name__ == "__main__":
    main()
