"""Grade the free local baseline against all labeled cases."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import evaluate, load_cases, quality_gate

if __name__ == "__main__":
    report = evaluate(load_cases())
    print("Free local evaluation; labels are checked by code, not an LLM judge.")
    print(json.dumps({"metrics": report.metrics, "gate": asdict(quality_gate(report))}, indent=2))
