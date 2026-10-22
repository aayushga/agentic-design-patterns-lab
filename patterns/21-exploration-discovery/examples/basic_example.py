"""Measure a baseline, explore a new setting, then test a promising combination."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app import explore, print_report

if __name__ == "__main__":
    print("Free discovery loop: aim for simulated latency <= 50ms.")
    print_report(explore())
    print("The combined cache+batch setting was tested, not assumed to be faster. Untested configurations remain unknown.")
