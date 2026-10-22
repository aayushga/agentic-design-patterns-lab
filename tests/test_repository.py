"""Repository contracts: runnable folders, local documentation, and private-state hygiene."""
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

import pytest

ROOT = Path(__file__).resolve().parents[1]
PATTERNS = sorted((ROOT/'patterns').glob('[0-9][0-9]-*'))


def test_complete_book_sequence_and_standalone_assets():
    assert [int(p.name[:2]) for p in PATTERNS] == list(range(1,22))
    for folder in PATTERNS:
        for path in ('README.md','app.py','requirements.txt','examples/basic_example.py',
                     'examples/advanced_example.py','openai_version/README.md',
                     'openai_version/requirements.txt','openai_version/.env.example'):
            assert (folder/path).is_file(), str(folder/path)
        assert list((folder/'tests').glob('test_*.py'))
        assert f'- [x] {folder.name[:2]}.' in (ROOT/'README.md').read_text()


def test_local_markdown_links_resolve():
    documents = [ROOT/'README.md',ROOT/'SECURITY.md',*(ROOT/'docs').glob('*.md'),
                 *[p for folder in PATTERNS for p in folder.rglob('*.md')]]
    for document in documents:
        for target in re.findall(r'\[[^\]\n]+\]\(([^)\n]+)\)',document.read_text()):
            if target.startswith(('http:','https:','#','mailto:')):
                continue
            local = unquote(target.split('#',1)[0].strip('<>'))
            assert (document.parent/local).exists(), f'{document.relative_to(ROOT)} -> {target}'


@pytest.mark.parametrize('path',['.env','.env.production','patterns/08-memory-management/.env.local',
    'patterns/08-memory-management/openai_version/memory.sqlite3','memory.sqlite3-wal','.coverage','.idea/workspace.xml'])
def test_private_local_state_is_ignored(path):
    result = subprocess.run(['git','check-ignore','--no-index','-v',path],cwd=ROOT,check=False,capture_output=True,text=True)
    matched = result.stdout.split('\t',1)[0].rsplit(':',1)[-1]
    assert result.returncode == 0 and matched and not matched.startswith('!')


def test_environment_examples_are_trackable_and_have_no_key():
    for folder in PATTERNS:
        path = folder/'openai_version/.env.example'
        values = dict(line.split('=',1) for line in path.read_text().splitlines() if line and not line.startswith('#'))
        assert values['OPENAI_API_KEY'].strip() == ''
        result = subprocess.run(['git','check-ignore','--no-index','-v',str(path.relative_to(ROOT))],cwd=ROOT,check=False,capture_output=True,text=True)
        matched = result.stdout.split('\t',1)[0].rsplit(':',1)[-1]
        assert result.returncode == 1 or matched.startswith('!')


def test_coverage_configuration_can_be_committed():
    result = subprocess.run(['git','check-ignore','--no-index','-v','.coveragerc'],cwd=ROOT,
                            check=False,capture_output=True,text=True)
    matched = result.stdout.split('\t',1)[0].rsplit(':',1)[-1]
    assert result.returncode == 1 or matched.startswith('!')
