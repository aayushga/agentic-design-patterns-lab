"""A temporary lookup failure recovers on the next bounded attempt."""
from pathlib import Path
import sys

if __package__:
    from ..app import print_run, run_support
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import print_run, run_support


if __name__ == "__main__":
    print_run(run_support(scenario="transient", sleep=lambda _: None, jitter=lambda: 1))
