"""A chosen pytest file reaches pytest with real Git on every platform."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "FIX-WINDOWS-GIT-DIFF-OPTION-ORDER"


@pytest.mark.platform
@pytest.mark.parametrize("adopted", [False, True], ids=["new", "earlier-adopted"])
def test_1_chosen_pytest_file_runs_with_git_options_before_paths(repo, adopted):
    # Audit: the real command must reach pytest for a path-valued selector.
    # Git rejects the old trailing -z before pytest starts. Existing picker tests
    # use commit selectors, which do not expose this path-order contract.
    # Real Git and pytest need no mock or production seam.
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    command = f'"{Path(sys.executable).as_posix()}" -m pytest "checks with spaces" -q'
    repo.write("forge.toml", f'version = "{version}"\ntest = ' + json.dumps(command) + "\n")
    chosen = "checks with spaces/test_chosen.py"
    repo.write(chosen, "def test_chosen():\n    assert True\n")
    repo.write("checks with spaces/test_other.py", "def test_other():\n    assert False\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up pytest client")
    repo.write(chosen, "def test_chosen():\n    assert 1 + 1 == 2\n")

    result = repo.forge("test", "--pytest", chosen)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert "git diff failed" not in result.stderr
