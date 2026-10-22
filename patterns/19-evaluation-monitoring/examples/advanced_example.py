"""Compare a controlled regression and show rolling alerts without real waiting."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import RollingMonitor, baseline_router, compare_reports, evaluate, load_cases, quality_gate, regressed_router


class DemoClock:
    def __init__(self):
        self.now = 0.0
    def __call__(self):
        return self.now


def simulated_report(cases, router, variant, seconds):
    clock = DemoClock()
    def timed(query):
        clock.now += seconds
        return router(query)
    return evaluate(cases, timed, variant=variant, clock=clock)


if __name__ == "__main__":
    print("Free simulation: baseline delay=10ms, candidate delay=250ms; no sleeping or model calls.")
    cases = load_cases()
    baseline = simulated_report(cases, baseline_router, "baseline", 0.010)
    candidate = simulated_report(cases, regressed_router, "candidate", 0.250)
    for report in (baseline, candidate):
        print(f"{report.variant}: accuracy={report.metrics['accuracy']:.0%}; errors={report.metrics['error_rate']:.1%}; p95={report.metrics['p95_latency_ms']:.1f}ms")
        print("  Gate:", asdict(quality_gate(report)))
    print("Comparison:", json.dumps(compare_reports(baseline, candidate)))
    monitor = RollingMonitor()
    previous = ()
    for observation in candidate.observations:
        alerts = monitor.observe(observation)
        if alerts != previous:
            print(f"Rolling window after {observation.case_id}: {alerts}")
            previous = alerts
    partial = evaluate(cases, max_cases=3)
    print("Budget-limited run:", partial.metrics["coverage"], asdict(quality_gate(partial)))
    print("Partial comparison:", compare_reports(baseline, partial))
