"""The quick command selects changed tests and Python-module references only."""
import json
import os
import subprocess
import sys
import tomllib
from pathlib import Path

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import (  # noqa: F401 (pytest fixtures)
    env, unsynced_up, _repo_adopted_on_the_previous_release,
)

STORY = "FIX-PICKER-TWO-RULES"


def _commit(repo, message):
    repo.git("add", "-A")
    # The fixture owns client setup, outside Forge's work lanes.
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", message)


def _configure(repo):
    path = repo.path / "forge.toml"
    settings = path.read_text("utf-8") if path.exists() else ""
    previous = tomllib.loads(settings).get("test")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    repo.write("forge.toml", settings.replace("test = " + json.dumps(previous),
                                             "test = " + json.dumps(command))
               if previous is not None else settings + "test = " + json.dumps(command) + "\n")


def _run(repo, base, launcher=None):
    return subprocess.run([sys.executable, str(launcher or repo.bin / "forge"),
                           "test", "--pytest", base], cwd=repo.path,
                          capture_output=True, text=True, timeout=120)


def test_1_changed_test_files_are_selected_without_their_readers(repo):
    # The old changed-path rule incorrectly selects a test that names another test.
    _configure(repo)
    repo.write("tests/test_changed.py", "def test_changed():\n    assert True\n")
    repo.write("tests/test_reader.py", "# tests/test_changed.py\n"
               "def test_reader():\n    assert False, 'Unchanged reader selected'\n")
    _commit(repo, "Set up changed test selection")
    base = repo.git("rev-parse", "HEAD")
    repo.write("tests/test_changed.py", "def test_changed():\n    assert 1 == 1\n")
    _commit(repo, "Change one test")
    result = _run(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Related tests: tests/test_changed.py"
    assert "1 passed" in result.stdout


def _module_selection(repo, monkeypatch, launcher=None):
    _configure(repo)
    monkeypatch.setenv("PYTHONPATH", os.pathsep.join(
        [str(repo.path / "src"), os.environ.get("PYTHONPATH", "")]))
    repo.write("src/shop/__init__.py", "")
    repo.write("src/shop/prices.py", "PRICE = 1\n")
    repo.write("docs/guide.md", "Before\n")
    references = {
        "changed": "",
        "import": "from shop.prices import PRICE",
        "package_import": "from shop import prices",
        "dotted": "# shop.prices",
        "path": "# shop/prices.py",
        "source_path": "# src/shop/prices.py",
        "package_path": "# src/shop/__init__.py",
    }
    for name, reference in references.items():
        repo.write(f"tests/test_{name}.py", reference + "\n"
                   f"def test_{name}():\n    assert True\n")
    for name, reference in {
        "prices": "# A filename matching a module is not a reference",
        "readme": "# README.md",
        "settings": "# forge.toml",
        "guide": "# docs/guide.md",
        "bare": "# prices",
        "other_module": "# shop.prices_other; shop/prices.py_extra",
    }.items():
        repo.write(f"tests/test_{name}.py", reference + "\n"
                   f"def test_{name}():\n    assert False, 'Unrelated test selected'\n")
    _commit(repo, "Set up module references and unrelated readers")
    base = repo.git("rev-parse", "HEAD")
    repo.write("src/shop/prices.py", "PRICE = 2\n")
    repo.write("src/shop/__init__.py", "# Changed package module\n")
    repo.write("tests/test_changed.py", "def test_changed():\n    assert 1 == 1\n")
    repo.write("README.md", "After\n")
    repo.write("docs/guide.md", "After\n")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", settings + "# Changed non-Python input\n")
    _commit(repo, "Change module and non-Python inputs")
    result = _run(repo, base, launcher)
    assert result.returncode == 0, result.stdout + result.stderr
    expected = sorted(f"tests/test_{name}.py" for name in references)
    assert result.stdout.splitlines()[0] == "Related tests: " + ", ".join(expected)
    assert "7 passed" in result.stdout


def test_2_only_imports_dotted_names_and_file_paths_select_module_tests(repo, monkeypatch):
    # Replaces filename and arbitrary changed-input readers with module references.
    _module_selection(repo, monkeypatch)


def test_3_new_clients_run_only_changed_tests_and_module_references(repo, gh, tmp_path, monkeypatch):
    client = _new_repo(repo, gh, tmp_path)
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    _module_selection(repo, monkeypatch)


def test_4_earlier_adopted_clients_get_two_rule_selection_after_upgrade(unsynced_up, monkeypatch):
    _repo_adopted_on_the_previous_release(unsynced_up)
    repo = unsynced_up.repo
    repo.path = unsynced_up.folder
    launcher = unsynced_up.tmp / "uvbin/forge"
    assert launcher.exists()
    _module_selection(repo, monkeypatch, launcher)
