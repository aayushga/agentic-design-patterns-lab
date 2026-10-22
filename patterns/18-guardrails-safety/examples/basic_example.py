"""Redact unnecessary personal data, then return an authorized order snapshot."""
from dataclasses import asdict
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import run_guarded_support

if __name__ == "__main__":
    result = run_guarded_support("Where is my order? My email is alex@example.test.", "ORD-101")
    print(json.dumps(asdict(result), indent=2))
