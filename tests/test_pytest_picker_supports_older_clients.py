"""The external picker works with old pytest and ships consistent setup guidance."""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-THE-QUICK-TEST-PICKER-BREAKS-ON-CLIENT-R"


@pytest.mark.parametrize("version", ["7.4.4", "8.1.2", "8.2.2"])
def test_1_picker_narrows_old_and_new_pytest_without_installing_forge(repo, version, monkeypatch):
    # Real pinned pytest: before 8.2, @selection.txt is treated as a missing test path.
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "--strict-markers")
    repo.write("forge.toml", "test = " + json.dumps(
        f'uv run --python 3.11 --isolated --no-project --with pytest=={version} '
        'python -m pytest "checks with spaces" "checks with spaces/test_unrelated.py::test_unrelated" -q') + "\n")
    repo.write("pytest.ini", "[pytest]\naddopts = --strict-config\n")
    repo.write("checks with spaces/test_changed.py", "import importlib.util, pytest\n"
               "def test_client(request):\n"
               f"    assert pytest.__version__ == {version!r}\n"
               "    assert importlib.util.find_spec('forge') is None\n"
               "    assert request.config.option.strict_markers\n"
               "    assert request.config.option.strict_config\n")
    repo.write("checks with spaces/test_unrelated.py", "raise RuntimeError('Unrelated collection')\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up pytest client")
    base = repo.git("rev-parse", "HEAD")
    path = repo.path / "checks with spaces/test_changed.py"
    path.write_text(path.read_text("utf-8") + "# changed\n", "utf-8")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change selected test")
    result = repo.forge("test", "--pytest", base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def _assert_external_setup(client):
    for host in (".codex", ".claude"):
        skill = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        setup = skill.split("8. Propose a `fast_test`", 1)[1].split("On a live app", 1)[0]
        assert "forge test --pytest {base}" in setup
        assert "Forge installed" not in setup
        assert "repo's Python runner" in setup
        assert "outside the project" in setup


def test_2_init_ships_consistent_external_picker_setup(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_external_setup(client)


def test_3_upgrade_ships_consistent_setup_to_a_previously_adopted_repo(unsynced_up):
    up = unsynced_up
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    up.repo.git("switch", "-qc", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-qm", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    result = up.run(RELEASE)
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_external_setup(up.folder)
