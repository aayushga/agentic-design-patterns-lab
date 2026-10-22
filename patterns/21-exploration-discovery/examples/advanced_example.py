"""Show failed experiments, cost/attempt bounds, and finite frontier exhaustion."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import explore, print_report

if __name__ == "__main__":
    print("Free fictional lab: harder 40ms target, six experiments, eight simulated cost units.")
    print_report(explore(target_latency_ms=40))
    limited = explore(max_experiments=8, cost_budget=2, target_latency_ms=40)
    print(f"\nSmall cost budget: {limited.stop_reason}; spent={limited.spent_cost_units}; best observed={limited.best_latency_ms}ms")
    exhausted = explore(max_experiments=8, cost_budget=16, target_latency_ms=1)
    print(f"Finite lab exhausted: {exhausted.stop_reason}; attempts={len(exhausted.trials)}; "
          f"valid={exhausted.successful_observations}; failed={exhausted.failed_config_ids}; target met={exhausted.target_met}")
    print("A failed experiment is not evidence of good performance. Best observed does not mean universally optimal.")
