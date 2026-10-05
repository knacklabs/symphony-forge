"""Quick tests run readers of changed files, including in initialized and upgraded clients."""
import json
import subprocess
import sys
import tomllib
from pathlib import Path

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import (  # noqa: F401 (pytest fixtures)
    RELEASE, env, unsynced_up, _repo_adopted_on_the_previous_release,
)

STORY = "FIX-THE-QUICK-TEST-RUN-SKIPS-TESTS-THAT-READ"


def _readers(repo, paths):
    config = repo.path / "forge.toml"
    settings = config.read_text("utf-8") if config.exists() else ""
    previous = tomllib.loads(settings).get("test")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    repo.write("forge.toml", settings.replace("test = " + json.dumps(previous),
                                             "test = " + json.dumps(command))
               if previous is not None else settings + "test = " + json.dumps(command) + "\n")
    for index, path in enumerate(paths):
        repo.write(path, "before\n")
        repo.write(f"tests/test_reader_{index}.py", "from pathlib import Path\n"
                   "def test_reader():\n"
                   f"    assert Path({json.dumps(path)}).read_text('utf-8') == 'after\\n'\n")
    repo.write("tests/test_unrelated.py", "# commands.md is only a basename\n"
               "def test_unrelated():\n    assert False, 'Unrelated test ran'\n")
    repo.git("add", "-A")
    # Seed the client's landed setup, as init/upgrade's owner does.
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Set up file readers")


def _change_and_run(repo, path, index=0, launcher=None):
    base = repo.git("rev-parse", "HEAD")
    repo.write(path, "after\n")
    repo.git("add", path)
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Change only a read file")
    result = subprocess.run([sys.executable, str(launcher or repo.bin / "forge"),
                             "test", "--pytest", base], cwd=repo.path,
                            capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == f"Related tests: tests/test_reader_{index}.py"
    assert "1 passed" in result.stdout


def test_1_docs_guides_and_workflow_only_changes_run_their_readers(repo):
    # Existing module-import coverage never changes a non-Python input. Each run
    # changes only one input; stale readers and the unrelated test fail if selected.
    paths = ["docs/commands.md", "src/forge/templates/shipped guide.md", ".github/workflows/tests.yml"]
    _readers(repo, paths)
    for index, path in enumerate(paths):
        _change_and_run(repo, path, index)


def test_2_init_gives_new_clients_the_file_reader_picker(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    _readers(repo, ["docs/commands.md"])
    _change_and_run(repo, "docs/commands.md")


def test_3_upgrade_gives_previously_adopted_clients_the_file_reader_picker(unsynced_up):
    _repo_adopted_on_the_previous_release(unsynced_up)
    repo = unsynced_up.repo
    repo.path = unsynced_up.folder
    _readers(repo, [".github/workflows/tests.yml"])
    launcher = unsynced_up.tmp / "uvbin/forge"
    assert launcher.exists()
    _change_and_run(repo, ".github/workflows/tests.yml", launcher=launcher)
