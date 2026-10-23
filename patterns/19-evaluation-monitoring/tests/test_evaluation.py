"""Offline checks for grading, comparison, budgets, and rolling observations."""
import importlib
import json
from dataclasses import replace

import pytest

app = importlib.import_module("patterns.19-evaluation-monitoring.app")


def run(router=app.baseline_router, **kwargs):
    return app.evaluate(app.load_cases(), router, **kwargs)


def test_baseline_and_intentional_regression():
    baseline, candidate = run(), run(app.regressed_router)
    assert baseline.metrics["accuracy"] == 1
    assert app.quality_gate(baseline).passed
    assert candidate.metrics["accuracy"] == .75
    assert candidate.metrics["error_rate"] == .125
    assert candidate.metrics["schema_valid_rate"] == .875
    assert candidate.metrics["per_route"]["billing"]["accuracy"] == 2 / 3
    assert app.compare_reports(baseline, candidate)["reasons"] == ["accuracy_regression"]


@pytest.mark.parametrize("budget", [0, 1, 3, 8, 50])
def test_budget_and_denominators(budget):
    queries = []
    def router(query):
        queries.append(query)
        return app.baseline_router(query)
    report = run(router, max_cases=budget)
    n = min(budget, 8)
    assert len(queries) == n
    assert report.metrics["coverage"] == n / 8
    assert report.metrics["task_success_rate"] == n / 8
    assert report.metrics["accuracy"] == (1 if n else None)
    assert len(report.observations) == 8
    assert sum(o.status == "not_run" for o in report.observations) == 8 - n
    if n < 8:
        assert not app.quality_gate(report).passed
        assert not app.compare_reports(run(), report)["comparable"]
    if not n:
        assert report.metrics["p95_latency_ms"] is None
        assert report.metrics["usage_complete"] is None


@pytest.mark.parametrize("budget", [-1, 51, True, 1.2, "3"])
def test_invalid_budgets(budget):
    with pytest.raises(ValueError):
        run(max_cases=budget)


@pytest.mark.parametrize("prediction", [None, "billing", {}, app.Prediction("private raw response"),
    app.Prediction(["billing"]), app.Prediction("billing", "secret exception")])
def test_invalid_predictions_are_errors_without_raw_output(prediction):
    report = run(lambda query: prediction)
    assert report.metrics["error_rate"] == 1
    assert report.metrics["accuracy"] == 0
    assert all(o.predicted_route is None for o in report.observations)
    assert "private raw response" not in repr(report)
    assert "secret exception" not in repr(report)


def test_abort_counts_current_error_and_preserves_remaining_cases():
    report = run(lambda query: app.Prediction(None, "provider_error", abort_run=True))
    assert report.metrics["attempted_count"] == 1
    assert report.metrics["error_rate"] == 1
    assert report.observations[0].error_code == "provider_error"
    assert all(o.error_code == "run_stopped" for o in report.observations[1:])


@pytest.mark.parametrize("input_tokens,output_tokens", [(None, None), (10, None), (True, 1),
    (-1, 4), (1, float("nan")), (1, 1000000001)])
def test_unknown_or_invalid_usage_is_not_zero(input_tokens, output_tokens):
    report = run(lambda q: app.Prediction("billing", input_tokens=input_tokens, output_tokens=output_tokens))
    assert report.metrics["usage_known_calls"] == 0
    assert report.metrics["known_input_tokens"] is None
    assert report.metrics["known_output_tokens"] is None
    assert report.metrics["usage_complete"] is False


def test_failed_generation_usage_and_zero_counts_are_retained():
    outputs = iter([app.Prediction(None, "generation_not_completed", 12, 30),
                    app.Prediction("billing", input_tokens=0, output_tokens=0)])
    report = run(lambda q: next(outputs), max_cases=2)
    assert report.metrics["usage_known_calls"] == 2
    assert report.metrics["known_input_tokens"] == 12
    assert report.metrics["known_output_tokens"] == 30
    assert report.metrics["usage_complete"] is True
    assert report.metrics["accuracy"] == .5


def test_latency_includes_failures_and_nearest_rank_p95():
    ticks = iter([0, .01, 1, 1.02, 2, 2.03, 3, 3.25])
    predictions = iter([app.Prediction("billing")] * 3 + [app.Prediction(None, "provider_error")])
    report = run(lambda q: next(predictions), max_cases=4, clock=lambda: next(ticks))
    assert report.metrics["p95_latency_ms"] == pytest.approx(250)
    assert report.metrics["mean_latency_ms"] == pytest.approx(77.5)
    assert report.timing_source == "injected_clock"


@pytest.mark.parametrize("end", [-1, float("nan"), float("inf")])
def test_invalid_clock_rejected(end):
    ticks = iter([0, end])
    with pytest.raises(ValueError, match="clock"):
        run(clock=lambda: next(ticks))


@pytest.mark.parametrize("change", [{"min_accuracy": float("nan")}, {"max_error_rate": True},
    {"min_coverage": -1}, {"max_p95_ms": float("inf")}, {"max_p95_ms": float("nan")},
    {"min_samples": 0}, {"min_samples": True}])
def test_invalid_thresholds(change):
    with pytest.raises(ValueError):
        app.Thresholds(**change)


def test_gate_boundaries_and_all_independent_failures():
    report = run(app.regressed_router)
    at_boundary = app.Thresholds(min_accuracy=.75, max_error_rate=.125,
                                 max_p95_ms=report.metrics["p95_latency_ms"])
    assert app.quality_gate(report, at_boundary).passed
    zero = run(max_cases=0)
    assert app.quality_gate(zero).reasons == ("insufficient_samples", "incomplete_coverage")
    assert not app.quality_gate(zero, app.Thresholds(min_coverage=0)).passed


def test_comparison_requires_same_dataset_and_complete_coverage():
    baseline = run()
    changed = list(app.load_cases())
    changed[0] = replace(changed[0], query="Different wording")
    other = app.evaluate(changed)
    result = app.compare_reports(baseline, other)
    assert result["reasons"] == ["different_datasets"]
    assert result["accuracy_delta"] is None
    reordered = app.evaluate(list(reversed(app.load_cases())))
    assert not app.compare_reports(baseline, reordered)["comparable"]
    # Accuracy remains comparable, timing is suppressed across measured/simulated runs.
    ticks = iter(range(16))
    simulated = run(clock=lambda: next(ticks))
    assert app.compare_reports(baseline, simulated)["p95_latency_delta_ms"] is None


def test_rolling_alerts_expire_and_not_run_does_not_fill_window():
    monitor = app.RollingMonitor()
    bad = run(lambda q: app.Prediction(None, "invalid_output")).observations[0]
    good = run().observations[0]
    skipped = run(max_cases=0).observations[0]
    for _ in range(3):
        assert monitor.observe(bad) == ()
    assert "high_error_rate" in monitor.observe(bad)
    monitor.observe(skipped)
    assert len(monitor.window) == 4
    for _ in range(4):
        alerts = monitor.observe(good)
    assert alerts == ()
    assert app.RollingMonitor().observe(good) == ()


@pytest.mark.parametrize("size", [0, 3, 51, True])
def test_invalid_monitor_window(size):
    with pytest.raises(ValueError):
        app.RollingMonitor(size)


def test_jsonl_is_append_only_and_omits_queries_and_exception_text(tmp_path):
    secret = "FICTIONAL_PRIVATE_QUERY"
    cases = [app.EvalCase("private_case", secret, "unknown")]
    def router(query):
        raise RuntimeError("PRIVATE_EXCEPTION")
    report = app.evaluate(cases, router)
    path = tmp_path / "logs" / "runs.jsonl"
    app.append_jsonl(report, path)
    app.append_jsonl(report, path)
    raw = path.read_text()
    assert secret not in raw and "PRIVATE_EXCEPTION" not in raw
    records = [json.loads(line) for line in raw.splitlines()]
    assert len(records) == 4
    assert [r["type"] for r in records] == ["case", "summary"] * 2
    assert all(r["schema_version"] == 1 and r["run_id"] == report.run_id for r in records)
    assert records[1]["metrics"]["error_rate"] == 1


@pytest.mark.parametrize("record", [{}, {"case_id": "a", "query": "q", "expected_route": "sales", "extra": 1},
    {"case_id": "a", "query": " ", "expected_route": "sales"},
    {"case_id": "a", "query": "q", "expected_route": "invalid"}])
def test_dataset_shape_validation(tmp_path, record):
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([record]))
    with pytest.raises(ValueError, match="dataset"):
        app.load_cases(path)


def test_dataset_bounds_uniqueness_and_utf8(tmp_path):
    cases = app.load_cases()
    for invalid in [[], list(cases) * 7, [cases[0], cases[0]], [None]]:
        with pytest.raises(ValueError):
            app.validate_cases(invalid)
    path = tmp_path / "large.json"
    path.write_bytes(b" " * 65537)
    with pytest.raises(ValueError, match="64 KiB"):
        app.load_cases(path)
    path.write_bytes(b"[\xff]")
    with pytest.raises(ValueError):
        app.load_cases(path)


@pytest.mark.parametrize("variant,limit,exit_code", [("baseline",8,0), ("regressed",8,1), ("baseline",3,1)])
def test_cli_explicit_gate_exit(monkeypatch, capsys, variant, limit, exit_code):
    monkeypatch.setattr("sys.argv", ["app.py", "--variant", variant, "--max-cases", str(limit), "--fail-on-gate"])
    if exit_code:
        with pytest.raises(SystemExit) as exc:
            app.main()
        assert exc.value.code == exit_code
    else:
        app.main()
    assert json.loads(capsys.readouterr().out)["gate"]["passed"] is (exit_code == 0)


@pytest.mark.parametrize("name,value", [("accuracy",float("nan")),("coverage",float("inf")),
    ("error_rate",float("nan")),("p95_latency_ms",-1),("p95_latency_ms",None),
    ("accuracy",True),("attempted_count",True),("coverage",10**400)])
def test_malformed_gate_metrics_fail_closed(name,value):
    metrics = dict(run().metrics)
    metrics[name] = value
    assert app.gate_metrics(metrics) == app.Gate(False,("invalid_metrics",))
    assert app.gate_metrics({}) == app.Gate(False,("invalid_metrics",))


def test_accuracy_drop_exactly_at_boundary_is_not_a_regression():
    cases = [app.EvalCase(f"case{i}","Invoice question","billing") for i in range(20)]
    baseline = app.evaluate(cases)
    predictions = iter([app.Prediction("billing")]*19+[app.Prediction("support")])
    candidate = app.evaluate(cases,lambda query:next(predictions))
    comparison = app.compare_reports(baseline,candidate,max_accuracy_drop=.05)
    assert comparison["accuracy_delta"] == pytest.approx(-.05)
    assert comparison["reasons"] == []
    assert app.compare_reports(baseline,candidate,max_accuracy_drop=.049)["reasons"] == ["accuracy_regression"]


def test_comparison_with_missing_metrics_is_rejected_before_reading_them():
    report = run()
    report.metrics.clear()
    assert app.compare_reports(report, run())["reasons"] == ["invalid_metrics"]
