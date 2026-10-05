"""The shipped fast command narrows real pytest, including configured inputs."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

STORY = "FIX-SIMPLIFY-FASTTEST"
ROOT = Path(__file__).resolve().parents[1]


def run_picker(repo, command, *, shared=False):
    repo.write("forge.toml", "test = " + json.dumps(command) + "\n")
    repo.write("src/shop/prices.py", "PRICE = 1\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Set up client")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("src/shop/prices.py", "PRICE = 2\n")
    if shared:
        repo.write("conftest.py", "# Shared input changed\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Change client")
    return subprocess.run(
        [sys.executable, str(repo.bin / "forge"), "test", "--pytest", base], cwd=repo.path,
        env={**os.environ, "PYTHONPATH": os.pathsep.join(
            [str(ROOT / "src"), str(repo.path / "src")])},
        text=True, capture_output=True, timeout=120)


@pytest.mark.parametrize("shared", [False, True], ids=["related", "full-fallback"])
@pytest.mark.parametrize("configuration", ["pytest.ini", "PYTEST_ADDOPTS", "launcher",
                                            "pyproject.toml", "pytest.toml", "smaller-cap",
                                            "explicit-config", "shell-environment"])
def test_1_caps_worker_counts_supplied_through_pytest_configuration(repo, shared, configuration, monkeypatch):
    cores = 4 if configuration == "smaller-cap" else 2
    repo.write("src/sitecustomize.py", f"import os\nos.cpu_count = lambda: {cores}\n")
    repo.write("tests/test_prices.py", "def test_count(request):\n"
               "    assert request.config.workerinput['workercount'] == 1\n")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    if configuration == "pytest.ini":
        repo.write("pytest.ini", "[pytest]\naddopts = -n 2\n")
    elif configuration == "PYTEST_ADDOPTS":
        monkeypatch.setenv("PYTEST_ADDOPTS", "-n 2")
    elif configuration == "pyproject.toml":
        repo.write("pyproject.toml", '[tool.pytest.ini_options]\naddopts = ["-n", "2"]\n')
    elif configuration == "pytest.toml":
        repo.write("pytest.toml", '[pytest]\naddopts = ["-n", "2"]\n')
    elif configuration == "smaller-cap":
        # Keep the repo's stricter cap while imposing Forge's machine ceiling.
        repo.write("pytest.ini", "[pytest]\naddopts = -n 4 --maxprocesses=1\n")
    elif configuration == "explicit-config":
        repo.write("config with spaces.ini", "[pytest]\naddopts = -n 2\n")
        command += ' -c "config with spaces.ini"'
    elif configuration == "shell-environment":
        command = ('set "PYTEST_ADDOPTS=-n 2" && ' if os.name == "nt"
                   else 'PYTEST_ADDOPTS="-n 2" ') + command
    else:
        # With no plugin, a launcher forwards pytest options from the command.
        # It may still replace PYTEST_ADDOPTS; the command-line cap wins.
        repo.write("run_tests.py", "import os, subprocess, sys\n"
                   "os.environ['PYTEST_ADDOPTS'] = '-n 2'\n"
                   "sys.exit(subprocess.call([sys.executable, '-m', 'pytest', 'tests', '-q', *sys.argv[1:]]))\n")
        command = f'"{Path(sys.executable).as_posix()}" run_tests.py -n 2'
    result = run_picker(repo, command, shared=shared)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_2_excludes_unrelated_tests_explicitly_named_by_full_command(repo):
    repo.write("tests/test_prices.py", "def test_prices():\n    assert True\n")
    repo.write("tests/test_unrelated.py", "raise RuntimeError('Unrelated file collected')\n"
               "def test_unrelated():\n    assert False\n")
    result = run_picker(repo, f'"{Path(sys.executable).as_posix()}" -m pytest '
                        'tests/test_prices.py tests/test_unrelated.py::test_unrelated -q')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout


def test_3_recognizes_source_prefixed_paths_and_package_relative_imports(repo):
    repo.write("src/shop/__init__.py", "")
    repo.write("src/shop/checks/__init__.py", "")
    repo.write("checks/test_path.py", "# src/shop/prices.py\n"
               "def test_path():\n    assert True\n")
    repo.write("src/shop/checks/test_import.py", "from .. import prices\n"
               "def test_import():\n    assert prices.PRICE == 2\n")
    repo.write("src/shop/test_direct.py", "from .prices import PRICE\n"
               "def test_direct():\n    assert PRICE == 2\n")
    result = run_picker(repo, f'"{Path(sys.executable).as_posix()}" -m pytest checks src/shop -q')
    assert result.returncode == 0, result.stdout + result.stderr
    assert "3 passed" in result.stdout
