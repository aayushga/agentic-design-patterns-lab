"""Fallback, invalid results, terminal failures, and graceful unavailability."""
from pathlib import Path
import sys

if __package__:
    from ..app import print_run, run_support
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import print_run, run_support


if __name__ == "__main__":
    for title, options in [
        ("OUTAGE: USE AN OLDER CACHE", {"scenario": "outage"}),
        ("MALFORMED RESULT: VALIDATE BEFORE USE", {"scenario": "malformed"}),
        ("ACCESS DENIED: DO NOT RETRY OR USE CACHE", {"scenario": "denied"}),
        ("NO FALLBACK: REPORT UNAVAILABILITY", {"scenario": "outage", "use_cache": False}),
    ]:
        print("\n" + title)
        print_run(run_support(**options, sleep=lambda _: None, jitter=lambda: 1))
