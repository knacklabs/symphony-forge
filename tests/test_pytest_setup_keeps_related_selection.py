"""A setup command and launcher retain the explicit pytest picker's selection."""
import json
import sys
from pathlib import Path

from test_fast_test_honors_pytest_inputs import run_picker

STORY = "FIX-RESTORE-PYTEST-SELECTION"


def test_1_setup_and_launcher_keep_related_selection(repo):
    repo.write("tests/test_prices.py", "# shop/prices.py\ndef test_prices():\n    assert True\n")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert False\n")
    repo.write("run_tests.py", "import subprocess, sys\n"
               "sys.exit(subprocess.call([sys.executable, '-m', 'pytest', 'tests', *sys.argv[1:]]))\n")
    python = json.dumps(Path(sys.executable).as_posix())
    result = run_picker(repo, f'{python} -c "pass" && {python} run_tests.py -q')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
