"""Check standalone pattern suites without maintaining a duplicated CI list."""
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    for folder in sorted((ROOT/'patterns').glob('[0-9][0-9]-*')):
        if folder.name.startswith('10-') and sys.version_info < (3,11):
            continue
        subprocess.run([sys.executable,'-B','-m','pytest','tests','-q'],cwd=folder,check=True)


if __name__ == '__main__':
    main()
