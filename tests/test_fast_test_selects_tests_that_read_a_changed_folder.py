"""The fast command selects a test that reads a folder when a file inside the folder changes.

Test audit: Forge's own `forge test --pytest <base>` command on a small repo, then on a copy of
Forge's own tests, so a change to the board's script files selects its browser tests. No seam.
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401

pytestmark = pytest.mark.platform

STORY = "FIX-BOARD-CHANGE-RUNS-BOARD-TESTS"
ROOT = Path(__file__).resolve().parents[1]


def selected_after_change(repo, changed):
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q --collect-only'  # double quotes: cmd.exe too
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


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_a_test_that_lists_a_folder_runs_in_the_pull_request_check_when_a_file_in_it_changes(
        env, tmp_path, monkeypatch, history):
    # The shipped `forge test --change` runs the client's real tests. A receipt from the folder
    # reader proves selection; a test that reads one other file of the folder must not run.
    _client(env.repo, env.gh, tmp_path, history)
    env.repo.git("switch", "-qc", "fix/check-folder-reader")
    env.repo.write(".factory/fixes/check-folder-reader.json", json.dumps({
        "kind": "fix", "branch": "fix/check-folder-reader", "status": "started",
        "why": "Check folder readers", "done_when": "Folder readers run"}))
    config = env.repo.path / "forge.toml"
    settings = re.sub(r"^(?:fast_test|always_test) = .*\n", "", config.read_text("utf-8"), flags=re.M)
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    config.write_text(re.sub(r"^test = .*", lambda _: "test = " + json.dumps(command), settings,
                             flags=re.M), "utf-8")
    env.repo.write("site/app.js", "// old\n")
    env.repo.write("site/other.js", "// other\n")
    env.repo.write("tests/test_lists_folder.py", "import os\nfrom pathlib import Path\n"
                   "SITE = Path(__file__).parents[1] / 'site'\n"
                   "def test_lists():\n    assert sorted(p.name for p in SITE.glob('*.js'))\n"
                   "    Path(os.environ['FOLDER_READER_RECEIPT']).write_text('ran')\n")
    env.repo.write("tests/test_reads_one_file.py", "from pathlib import Path\n"
                   "ONE = Path(__file__).parents[1] / 'site' / 'other.js'\n"
                   "def test_one():\n    assert ONE.read_text() == 'never'\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Add folder reader")
    base = env.repo.git("rev-parse", "HEAD")
    env.repo.git("update-ref", "refs/remotes/origin/main", base)
    env.repo.write("site/app.js", "// new\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Change a script")
    receipt = tmp_path / "folder-reader-ran"
    monkeypatch.setenv("FOLDER_READER_RECEIPT", str(receipt))
    monkeypatch.setenv("BASE_SHA", base)
    ran = env.repo.forge("test", "--change")
    assert ran.returncode == 0, ran.stdout + ran.stderr
    assert receipt.exists(), ran.stdout + ran.stderr


def test_2_a_change_to_the_boards_script_files_selects_all_its_browser_tests(repo):
    shutil.copytree(ROOT / "tests", repo.path / "tests")
    shutil.copytree(ROOT / "src", repo.path / "src")
    selected = selected_after_change(repo, "src/forge/board_app/item.js")
    browser = {f"tests/{path.name}" for path in (ROOT / "tests").glob("test_board*.py")
               if "from test_board_server import" in path.read_text("utf-8")}
    assert "tests/test_board_item_tab_in_address.py" in browser
    assert browser <= set(selected), sorted(browser - set(selected))
