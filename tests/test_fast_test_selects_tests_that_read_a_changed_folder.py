"""The fast command selects a test that reads a folder when a file inside the folder changes.

Test audit: Forge's own `forge test --pytest <base>` command on a small repo, then on a copy of
Forge's own tests, so a change to the board's script files selects its browser tests. No seam.
"""
import json
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.platform

STORY = "FIX-BOARD-CHANGE-RUNS-BOARD-TESTS"
ROOT = Path(__file__).resolve().parents[1]


def selected_after_change(repo, changed):
    command = shlex.join([Path(sys.executable).as_posix(), "-m", "pytest", "tests", "-q", "--collect-only"])
    repo.write("forge.toml", "test = " + json.dumps(command) + "\n")
    repo.write(changed, "// before\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Set up")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write(changed, "// after\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Change a script")
    result = subprocess.run([sys.executable, str(repo.bin / "forge"), "test", "--pytest", base], cwd=repo.path,
                            env={**{k: v for k, v in os.environ.items() if k != "PYTEST_PLUGINS"},
                                 "PYTHONPATH": str(ROOT / "src")},
                            capture_output=True, text=True, timeout=120)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout.splitlines()[0].removeprefix("Related tests: ").split(", ")


def test_1_a_test_that_reads_a_folder_is_selected_when_a_file_in_it_changes(repo):
    repo.write("tests/test_reads_folder.py", "from pathlib import Path\n"
               "ASSETS = Path(__file__).parent.parent / 'src' / 'site' / 'assets'\n"
               "def test_reads():\n    assert ASSETS\n")
    repo.write("tests/test_other.py", "def test_other():\n    assert True\n")
    assert selected_after_change(repo, "src/site/assets/app.js") == ["tests/test_reads_folder.py"]


def test_2_a_change_to_the_boards_script_files_selects_its_browser_tests(repo):
    shutil.copytree(ROOT / "tests", repo.path / "tests")
    shutil.copytree(ROOT / "src", repo.path / "src")
    selected = selected_after_change(repo, "src/forge/board_app/item.js")
    assert "tests/test_board_item_tab_in_address.py" in selected
    assert "tests/test_board_half_screen_width.py" in selected
