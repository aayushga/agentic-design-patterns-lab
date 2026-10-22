"""Offline evidence, frontier, budget, and proposal validation checks."""
import importlib
from dataclasses import asdict
import json

import pytest

app = importlib.import_module("patterns.21-exploration-discovery.app")


def test_basic_discovery_leaves_unknowns_and_measures_combination():
    result = app.explore()
    assert [t.config_id for t in result.trials] == ["cfg-00","cfg-01","cfg-03"]
    assert [t.latency_ms for t in result.trials] == [120,80,45]
    assert result.stop_reason == "target_met" and result.target_met
    assert result.best_config_id == "cfg-03" and result.best_latency_ms == 45
    assert result.spent_cost_units == result.remaining_cost_units == 4
    assert result.attempted_coverage == 3/8 and result.successful_observations == 3
    assert len(result.untried_config_ids) == 5


def test_advanced_failure_consumes_budget_without_becoming_evidence():
    result = app.explore(target_latency_ms=40)
    assert [t.config_id for t in result.trials] == ["cfg-00","cfg-01","cfg-03","cfg-07","cfg-05","cfg-04"]
    failed = result.trials[3]
    assert failed.status == "failed" and failed.error_code == "experiment_error"
    assert failed.latency_ms is None and not failed.improved_best
    assert failed.cost_units == 2
    assert result.spent_cost_units == 8 and result.remaining_cost_units == 0
    assert result.successful_observations == 5 and result.attempted_coverage == .75
    assert result.failed_config_ids == ("cfg-07",)
    assert result.untried_config_ids == ("cfg-02","cfg-06")
    assert not result.target_met and result.stop_reason == "experiment_limit"
    assert result.best_config_id == "cfg-03"


def test_cost_cap_and_frontier_exhaustion_have_distinct_stops():
    limited = app.explore(max_experiments=8,cost_budget=2,target_latency_ms=40)
    assert limited.stop_reason == "cost_limit" and limited.spent_cost_units == 2
    assert limited.best_latency_ms == 80 and limited.frontier_ids
    full = app.explore(max_experiments=8,cost_budget=16,target_latency_ms=1)
    assert full.stop_reason == "frontier_exhausted" and not full.target_met
    assert len(full.trials) == 8 and full.successful_observations == 7
    assert full.attempted_coverage == 1 and not full.untried_config_ids and not full.frontier_ids


def test_zero_budgets_never_execute_or_propose():
    def forbidden(*args):
        raise AssertionError("Must not be called")
    for kwargs,reason in [({"max_experiments":0},"experiment_limit"),({"cost_budget":0},"cost_limit")]:
        result = app.explore(experiment=forbidden,proposer=forbidden,**kwargs)
        assert result.stop_reason == reason and not result.trials
        assert result.best_latency_ms is None and result.best_config_id is None
        assert result.successful_observations == 0 and result.attempted_coverage == 0
        assert result.spent_cost_units == 0 and len(result.untried_config_ids) == 8


def test_measured_target_wins_over_limits_at_exact_boundary():
    result = app.explore(max_experiments=1,cost_budget=1,target_latency_ms=120)
    assert result.stop_reason == "target_met" and result.remaining_cost_units == 0


def test_frontier_expands_from_observations_not_all_catalog_entries():
    calls = []
    def proposer(offered,trials,target):
        calls.append((offered,trials))
        assert [t.config_id for t in trials] == ["cfg-00"]
        assert {c.configuration.config_id for c in offered} == {"cfg-01","cfg-02","cfg-04"}
        assert all(c.novel_values == 1 and c.best_parent_latency_ms == 120 for c in offered)
        return app.Proposal("cfg-04")
    result = app.explore(max_experiments=2,proposer=proposer,target_latency_ms=1)
    assert len(calls) == 1  # Baseline has one candidate, so no proposer is needed.
    assert result.trials[1].config_id == "cfg-04"
    assert result.trials[1].selection_source == "proposal"
    assert result.trials[1].latency_ms == 110


def test_selection_changes_when_new_evidence_changes_parent_quality():
    def slower_cache(config):
        return app.Measurement(160) if config.config_id == "cfg-01" else app.simulate_experiment(config)
    original = app.explore(max_experiments=3,target_latency_ms=1)
    changed = app.explore(max_experiments=3,target_latency_ms=1,experiment=slower_cache)
    assert original.trials[-1].config_id == "cfg-03"
    assert changed.trials[-1].config_id == "cfg-02"


def test_failed_baseline_does_not_expand_or_claim_all_settings_were_tested():
    def backend(config):
        raise RuntimeError("PRIVATE_BACKEND_ERROR")
    report = app.explore(experiment=backend)
    assert len(report.trials) == 1 and report.spent_cost_units == 1
    assert report.stop_reason == "frontier_exhausted"
    assert report.successful_observations == 0 and report.best_latency_ms is None
    assert len(report.untried_config_ids) == 7 and not report.frontier_ids
    assert "PRIVATE_BACKEND_ERROR" not in json.dumps(asdict(report))


@pytest.mark.parametrize("measurement", [None,45,{"latency_ms":1},app.Measurement(True),
    app.Measurement(0),app.Measurement(-1),app.Measurement(10001),app.Measurement(float("nan")),
    app.Measurement(float("inf")),app.Measurement(2.5)])
def test_invalid_measurements_are_charged_failures_not_facts(measurement):
    result = app.explore(experiment=lambda config:measurement)
    assert result.trials[0].error_code == "invalid_measurement"
    assert result.trials[0].latency_ms is None and not result.target_met
    assert result.successful_observations == 0 and result.spent_cost_units == 1


@pytest.mark.parametrize("proposal", [None,"cfg-01",app.Proposal("cfg-00"),app.Proposal("cfg-07"),
    app.Proposal("not-in-catalog"),app.Proposal(["cfg-01"]),app.Proposal("cfg-01","PRIVATE_ERROR")])
def test_invalid_duplicate_or_unoffered_proposals_fall_back_safely(proposal):
    result = app.explore(max_experiments=2,proposer=lambda *args:proposal)
    trial = result.trials[-1]
    assert trial.config_id == "cfg-01" and trial.selection_source == "rules_fallback"
    assert trial.selection_reason == "invalid_proposal"
    assert "PRIVATE_ERROR" not in repr(result)


def test_proposer_failure_is_separate_from_experiment_failure():
    def proposer(*args):
        raise RuntimeError("PRIVATE_PROPOSER_ERROR")
    result = app.explore(proposer=proposer)
    assert result.target_met and result.successful_observations == 3
    assert not result.failed_config_ids
    assert result.trials[1].selection_reason == "proposer_error"
    assert "PRIVATE_PROPOSER_ERROR" not in repr(result)


def test_setup_errors_propagate_without_becoming_measurements():
    def proposer(*args):
        raise app.ProposerConfigurationError("Missing setup")
    with pytest.raises(app.ProposerConfigurationError,match="Missing setup"):
        app.explore(proposer=proposer)


@pytest.mark.parametrize("budget", [1,2,3,4,5,8,16])
def test_attempt_and_cost_invariants_across_budgets(budget):
    result = app.explore(max_experiments=8,cost_budget=budget,target_latency_ms=1)
    ids = [t.config_id for t in result.trials]
    assert len(ids) == len(set(ids)) <= 8
    assert result.spent_cost_units == sum(t.cost_units for t in result.trials) <= budget
    assert result.remaining_cost_units == budget-result.spent_cost_units
    assert set(ids).isdisjoint(result.untried_config_ids)
    assert set(ids)|set(result.untried_config_ids) == {c.config_id for c in app.CATALOG}
    assert all(t.configuration.cost_units == t.cost_units for t in result.trials)
    assert result.best_latency_ms == min(t.latency_ms for t in result.trials if t.latency_ms is not None)
    json.dumps(asdict(result),allow_nan=False)


def test_failed_experiment_does_not_mark_a_feature_value_observed():
    report = app.explore(target_latency_ms=40,max_experiments=4)
    observations = tuple(app.Observation(t.configuration,t.latency_ms) for t in report.trials if t.status == "observed")
    candidate = app.rank_frontier((app.CATALOG[5],),observations,16)[0]
    assert candidate.novel_values == 1  # Failed cfg-07 did not establish compression=True performance.


def test_neighbors_are_unique_single_changes_and_order_is_deterministic():
    for config in app.CATALOG:
        values = app.neighbors(config)
        assert len(set(values)) == 3 and config not in values
        assert all(len(app.feature_values(config)-app.feature_values(n)) == 1 for n in values)
        assert all(config in app.neighbors(n) for n in values)
    assert app.explore() == app.explore()


@pytest.mark.parametrize("kwargs", [{"cache":1},{"compression":"yes"},{"batch_size":True},
    {"batch_size":2},{"batch_size":4.0}])
def test_invalid_configurations_rejected(kwargs):
    with pytest.raises(ValueError):
        app.Configuration(**kwargs)


@pytest.mark.parametrize("kwargs", [{"max_experiments":-1},{"max_experiments":9},{"max_experiments":True},
    {"cost_budget":-1},{"cost_budget":17},{"cost_budget":1.5},{"target_latency_ms":0},
    {"target_latency_ms":10001},{"target_latency_ms":float("nan")},{"target_latency_ms":True}])
def test_invalid_host_limits_precede_any_work(kwargs):
    with pytest.raises(ValueError):
        app.explore(**kwargs)


def test_cli_zero_and_invalid_budget(monkeypatch,capsys):
    monkeypatch.setattr("sys.argv",["app.py","--max-experiments","0"])
    app.main()
    assert "Best observed: none" in capsys.readouterr().out
    monkeypatch.setattr("sys.argv",["app.py","--cost-budget","-1"])
    with pytest.raises(SystemExit,match="cost_budget"):
        app.main()
