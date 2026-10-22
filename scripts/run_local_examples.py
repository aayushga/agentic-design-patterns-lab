"""Run every default/local demo with credentials removed and sockets blocked."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WRAPPER = """
import runpy, socket, sys
path = sys.argv[1]
sys.argv = [path]
def blocked(*args, **kwargs):
    raise RuntimeError('Network connections are disabled for local demos')
socket.socket.connect = blocked
socket.socket.connect_ex = blocked
runpy.run_path(path, run_name='__main__')
"""


def main():
    env = {key:value for key,value in os.environ.items() if not key.startswith('OPENAI_')}
    passed = 0
    for folder in sorted((ROOT/'patterns').glob('[0-9][0-9]-*')):
        if folder.name.startswith('10-') and sys.version_info < (3,11):
            continue
        for relative in ('app.py','examples/basic_example.py','examples/advanced_example.py'):
            path = folder/relative
            try:
                result = subprocess.run([sys.executable,'-B','-c',WRAPPER,str(path)],
                    cwd=ROOT,env=env,capture_output=True,text=True,timeout=45,check=False)
            except subprocess.TimeoutExpired:
                raise SystemExit(f'{path.relative_to(ROOT)} exceeded 45 seconds') from None
            if result.returncode:
                print(result.stdout)
                print(result.stderr,file=sys.stderr)
                raise SystemExit(f'{path.relative_to(ROOT)} failed: {result.returncode}')
            passed += 1
    print(f'{passed} local demos passed with socket connections blocked and OpenAI variables removed.')


if __name__ == '__main__':
    main()
