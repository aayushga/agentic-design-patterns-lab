"""Retrieve a fictional policy and answer with exact cited excerpts."""
from pathlib import Path
import sys

if __package__:
    from ..app import print_run, run_rag
else:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app import print_run, run_rag


if __name__ == "__main__":
    print_run(run_rag("Within how many days can I request a refund?", top_k=1))
