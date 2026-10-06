"""Manifest metadata narrows real pytest; Forge never refreshes a client's uv lock.

The old contract ran everything for any pyproject edit and let uv resolve again.
These tests use real pytest and uv, including setup and an earlier adoption.
"""
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_upgrade_command import (  # noqa: F401 (fixtures)
    env, unsynced_up, _repo_adopted_on_the_previous_release,
)

STORY = "FIX-ANY-PYPROJECT-TOML-CHANGE-MAKES-FORGE-TE"
UV = shutil.which("uv")
MANIFEST = '[project]\nname = "shop"\nversion = "2.0"\ndependencies = []\n'


def configure(repo, *, uv=False):
    path = repo.path / "forge.toml"
    settings = path.read_text("utf-8") if path.exists() else ""
    previous = tomllib.loads(settings).get("test")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    repo.write("pyproject.toml", MANIFEST)
    repo.write("tests/test_manifest.py", "# pyproject.toml\n"
               "def test_manifest():\n    assert True\n")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert True\n")
    if uv:
        if not UV:
            pytest.skip("The real uv executable is required for lockfile preservation")
        repo.write(".gitignore", ".venv/\n__pycache__/\n.pytest_cache/\n")
        uv_command = f'"{Path(UV).as_posix()}" --offline --no-cache'
        python = f'--python "{Path(sys.executable).as_posix()}"'
        locked = subprocess.run([UV, "lock", "--offline", "--no-cache", "--python", sys.executable],
                                cwd=repo.path, capture_output=True, text=True,
                                env={**os.environ, "UV_FROZEN": "0"}, timeout=30)
        assert locked.returncode == 0, locked.stdout + locked.stderr
        # An older worktree's manifest disagrees with the recorded lock's root version.
        repo.write("pyproject.toml", MANIFEST.replace('version = "2.0"', 'version = "1.0"'))
        repo.write("run_tests.py", "import subprocess, sys\n"
                   f"sys.exit(subprocess.call([{json.dumps(sys.executable)}, '-m', 'pytest', "
                   "'tests', '-q', *sys.argv[1:]]))\n")
        command = f'{uv_command} sync {python} && {uv_command} run {python} python run_tests.py'
    repo.write("forge.toml", settings.replace("test = " + json.dumps(previous),
                                             "test = " + json.dumps(command))
               if previous is not None else settings + "test = " + json.dumps(command) + "\n")
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Set up client tests")
    return repo.git("rev-parse", "HEAD")


def pick(repo, base, *, launcher=None):
    return subprocess.run([sys.executable, str(launcher or repo.bin / "forge"),
                           "test", "--pytest", base], cwd=repo.path,
                          capture_output=True, text=True, timeout=60)


def commit_manifest(repo, text):
    repo.write("pyproject.toml", text)
    repo.git("add", "pyproject.toml")
    repo.git("-c", f"core.hooksPath={repo.path / '.git/no-hooks'}", "commit", "-qm", "Change manifest")


@pytest.mark.parametrize("change,full", [
    ('# Comment\n', False),
    ('[tool.forge]\nline_ceiling = 11000\n', False),
    ('[tool.ruff]\nline-length = 100\n', False),
    ('[tool.poetry]\ndescription = "New description"\n', False),
    ('[tool.uv]\ncache-keys = [{file = "version.py"}]\n', False),
    ('description = "New description"\n', False),
    ('version', False),
    ('dependencies', True),
    ('requires-python = ">=3.11"\n', True),
    ('[project.optional-dependencies]\ntest = ["pytest"]\n', True),
    ('[dependency-groups]\ndev = ["pytest"]\n', True),
    ('[build-system]\nrequires = ["hatchling"]\n', True),
    ('[tool.uv]\nconstraint-dependencies = ["pytest<9"]\n', True),
    ('[tool.uv]\nbuild-constraint-dependencies = ["setuptools<80"]\n', True),
    ('[tool.uv.extra-build-dependencies]\nshop = ["setuptools"]\n', True),
    ('[[tool.uv.dependency-metadata]]\nname = "shop"\nrequires-dist = ["pytest"]\n', True),
    ('[tool.uv.dependency-groups]\ndev = {requires-python = ">=3.12"}\n', True),
    ('[tool.uv]\nresolution = "lowest"\n', True),
    ('[tool.uv]\nprerelease = "allow"\n', True),
    ('[tool.uv]\nexclude-newer = "2026-01-01T00:00:00Z"\n', True),
    ('[tool.uv]\nindex-url = "https://example.com/simple"\n', True),
    ('[tool.uv]\nextra-index-url = ["https://example.com/simple"]\n', True),
    ('[tool.uv.exclude-newer-package]\npytest = "2026-01-01T00:00:00Z"\n', True),
    ('[tool.uv]\nfork-strategy = "fewest"\n', True),
    ('[tool.uv]\nindex-strategy = "unsafe-best-match"\n', True),
    ('[tool.uv]\nfind-links = ["https://example.com/wheels"]\n', True),
    ('[tool.uv]\nno-index = true\n', True),
    ('[tool.uv]\nno-sources = true\n', True),
    ('[tool.uv]\nno-sources-package = ["pytest"]\n', True),
    ('[tool.uv.prerelease-package]\npytest = "allow"\n', True),
    ('[tool.uv.minimum-libc-version]\nglibc = "2.28"\n', True),
    ('[tool.uv.config-settings]\neditable_mode = "compat"\n', True),
    ('[tool.uv.config-settings-package]\nshop = {editable_mode = "compat"}\n', True),
    ('[tool.uv.extra-build-variables]\nshop = {USE_CUDA = "0"}\n', True),
    ('[tool.uv]\nno-build-isolation = true\n', True),
    ('[tool.uv]\nno-build-isolation-package = ["shop"]\n', True),
    ('[tool.uv]\nno-build = true\n', True),
    ('[tool.uv]\nno-build-package = ["shop"]\n', True),
    ('[tool.uv]\nno-binary = true\n', True),
    ('[tool.uv]\nno-binary-package = ["shop"]\n', True),
    ('[tool.uv]\nupgrade = true\n', True),
    ('[tool.uv]\nupgrade-package = ["pytest"]\n', True),
    ('[tool.uv]\nmanaged = false\n', True),
    ('[tool.uv]\npackage = true\n', True),
    ('[tool.poetry.dependencies]\npytest = "*"\n', True),
    ('[tool.pdm.dev-dependencies]\ntest = ["pytest"]\n', True),
    ('[tool.setuptools.dynamic]\ndependencies = {file = "requirements.txt"}\n', True),
    ('dynamic = ["dependencies"]\n', True),
    ('[tool.pytest.ini_options]\naddopts = "-v"\n', True),
    ('[tool.pytest]\naddopts = ["-v"]\n', True),
    ('malformed', True),
    ('added', False),
    ('removed', False),
    ('removed-dependencies', True),
    ('removed-pytest', True),
])
def test_1_only_dependency_or_pytest_manifest_changes_run_every_test(repo, change, full):
    base = configure(repo)
    if change == "added":
        repo.git("rm", "pyproject.toml")
        repo.git("commit", "-qm", "Start without packaging metadata")
        base = repo.git("rev-parse", "HEAD")
    elif change in ("removed-dependencies", "removed-pytest"):
        original = (MANIFEST.replace("dependencies = []", 'dependencies = ["pytest"]')
                    if change == "removed-dependencies" else
                    MANIFEST + '[tool.pytest.ini_options]\naddopts = "-v"\n')
        commit_manifest(repo, original)
        base = repo.git("rev-parse", "HEAD")
    text = MANIFEST + change
    if change == "version":
        text = MANIFEST.replace('version = "2.0"', 'version = "3.0"')
    elif change == "dependencies":
        text = MANIFEST.replace("dependencies = []", 'dependencies = ["pytest"]')
    elif change == "added":
        text = MANIFEST
    elif change == "malformed" or change.startswith("removed"):
        # Missing snapshots stay conservative; malformed input is reported by pytest.
        repo.write("pytest.ini", "[pytest]\n")
        text = "[broken" if change == "malformed" else ""
    commit_manifest(repo, text)
    if change.startswith("removed"):
        repo.git("rm", "pyproject.toml")
        repo.git("commit", "-qm", "Remove manifest")
    result = pick(repo, base)
    if change == "malformed":
        assert result.returncode == 4, result.stdout + result.stderr
        assert "Shared test inputs changed" in result.stdout
        assert "Expected ']'" in result.stderr and "Traceback" not in result.stderr
        return
    assert result.returncode == 0, result.stdout + result.stderr
    assert ("2 passed" if full else "1 passed") in result.stdout, result.stdout
    assert ("Shared test inputs changed" in result.stdout) == full


@pytest.mark.parametrize("case", ["success", "failed-tests", "missing-lock"])
def test_2_uv_setup_and_test_runs_keep_an_older_worktrees_lock_unchanged(repo, monkeypatch, case):
    monkeypatch.setenv("UV_FROZEN", "0")  # Forge's policy wins over the caller's environment.
    base = configure(repo, uv=True)
    lock = (repo.path / "uv.lock").read_bytes()
    commit_manifest(repo, (repo.path / "pyproject.toml").read_text("utf-8") + "# Metadata only\n")
    if case == "failed-tests":
        repo.write("tests/test_manifest.py", "# pyproject.toml\n"
                   "def test_manifest():\n    assert False, 'Client test failed'\n")
        repo.git("add", "tests/test_manifest.py")
        repo.git("commit", "-qm", "Make client test fail")
    elif case == "missing-lock":
        repo.git("rm", "uv.lock")
        repo.git("commit", "-qm", "Remove lock")
    result = pick(repo, base)
    assert result.returncode == {"success": 0, "failed-tests": 1, "missing-lock": 2}[case], result.stdout + result.stderr
    if case == "missing-lock":
        assert not (repo.path / "uv.lock").exists()
    else:
        assert (repo.path / "uv.lock").read_bytes() == lock
        assert ("1 failed" if case == "failed-tests" else "1 passed") in result.stdout
    assert repo.git("status", "--porcelain") == ""


def check_generated_ci(repo, lock, *, launcher=None):
    if repo.git("branch", "--show-current") == "main":
        repo.git("switch", "-qc", "fix/check-client-ci")
    synced = subprocess.run([sys.executable, str(launcher or repo.bin / "forge"), "sync"],
                            cwd=repo.path, capture_output=True, text=True, timeout=60)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    tests_job = workflow.split("  tests:\n", 1)[1].split("  forge-pr-check:\n", 1)[0]
    frozen = re.search(r"^      UV_FROZEN: '([^']+)'$", tests_job, re.M)
    assert frozen, tests_job
    command = json.loads(re.search(r'^      - run: (".*")$', tests_job, re.M)[1])
    result = subprocess.run(command, shell=True, cwd=repo.path, capture_output=True, text=True,
                            env={**os.environ, "UV_FROZEN": frozen[1]}, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "2 passed" in result.stdout
    assert (repo.path / "uv.lock").read_bytes() == lock


def test_3_new_clients_get_related_manifest_tests_and_frozen_uv(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    (client / "pyproject.toml").write_text(MANIFEST, "utf-8")
    initialized = repo.forge("init", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.path = client
    base = configure(repo, uv=True)
    lock = (client / "uv.lock").read_bytes()
    commit_manifest(repo, (client / "pyproject.toml").read_text("utf-8") + "# Metadata only\n")
    result = pick(repo, base)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert (client / "uv.lock").read_bytes() == lock
    check_generated_ci(repo, lock)


def test_4_earlier_adopted_clients_get_related_manifest_tests_and_frozen_uv(unsynced_up):
    _repo_adopted_on_the_previous_release(unsynced_up)
    repo = unsynced_up.repo
    repo.path = unsynced_up.folder
    base = configure(repo, uv=True)
    lock = (repo.path / "uv.lock").read_bytes()
    commit_manifest(repo, (repo.path / "pyproject.toml").read_text("utf-8") + "# Metadata only\n")
    result = pick(repo, base, launcher=unsynced_up.tmp / "uvbin/forge")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert (repo.path / "uv.lock").read_bytes() == lock
    check_generated_ci(repo, lock, launcher=unsynced_up.tmp / "uvbin/forge")
