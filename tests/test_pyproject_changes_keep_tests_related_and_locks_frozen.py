"""Manifest metadata narrows real pytest; Forge never refreshes a client's uv lock.

Only explicit harmless lines narrow tests; unknown sections fail closed.
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
    ('version', False),
    ('description = "New description"\n', False),
    ('description = """\nNew multiline\ndescription\n"""\n', False),
    ('[tool.hatch.build]\ninclude = ["src/shop"]\n', False),
    ('[tool.hatch.build]\nexclude = ["docs"]\n', False),
    ('[tool.hatch.build]\nforce-include = {"assets" = "shop/assets"}\n', False),
    ('[tool.hatch.build.force-include]\n"assets" = "shop/assets"\n', False),
    ('[tool.hatch.build.targets.wheel]\ninclude = ["src/shop"]\n', False),
    ('[tool.hatch.build.targets.sdist]\ninclude = ["src/shop"]\n', False),
    ('[tool.hatch.build]\ninclude = [\n  "src/shop",\n  # Packaged files\n  "assets",\n]\n', False),
    ('removed-include', False),
    ('# Comment outside a safe value\n', True),
    ('[tool.forge]\nline_ceiling = 11000\n', True),
    ('[tool.ruff]\nline-length = 100\n', True),
    ('[tool.uv]\ncache-keys = [{file = "version.py"}]\n', True),
    ('[tool.tox.env_run_base]\ndeps = ["pytest"]\n', True),
    ('[tool.tox.env.test]\ndeps = ["pytest"]\n', True),
    ('[tool.flit.metadata]\nrequires = ["pytest"]\n', True),
    ('[tool.rye]\ndev-dependencies = ["pytest"]\n', True),
    ('[tool.unfamiliar]\nunknown = "anything"\n', True),
    ('[tool.hatch.build]\ninclude = ["src/shop"]\ndependencies = ["wheel"]\n', True),
    ('[tool.hatch.build]\ninclude = ["src/shop"]\n'
     '[tool.hatch.build.hooks.custom]\ndependencies = ["wheel"]\n', True),
    ('[tool.hatch.build]\ninclude = ["src/shop"]\n'
     '[tool.pytest.ini_options]\naddopts = "-v"\n', True),
    ('[tool.unfamiliar]\ntext = """\n[project]\nversion = "pretend"\n"""\n', True),
    ('[tool.hatch.build]\ninclude = 42\n', True),
    ('requires-python = ">=3.11"\n', True),
    ('dependencies', True),
    ('moved-section', True),
    ('dotted-version', True),  # Unsupported spellings conservatively run everything.
    ('malformed', True),
    ('added', True),
    ('removed', True),
])
def test_1_only_known_harmless_manifest_lines_keep_tests_related(repo, change, full):
    base = configure(repo)
    if change == "added":
        repo.git("rm", "pyproject.toml")
        repo.git("commit", "-qm", "Start without packaging metadata")
        base = repo.git("rev-parse", "HEAD")
    elif change == "removed-include":
        commit_manifest(repo, MANIFEST + '[tool.hatch.build]\ninclude = ["src/shop"]\n')
        base = repo.git("rev-parse", "HEAD")
    elif change == "moved-section":
        commit_manifest(repo, MANIFEST + '[tool.hatch.build]\ninclude = ["src/shop"]\n')
        base = repo.git("rev-parse", "HEAD")
    text = MANIFEST + change
    if change == "version":
        text = MANIFEST.replace('version = "2.0"', 'version = "3.0"')
    elif change == "dependencies":
        text = MANIFEST.replace("dependencies = []", 'dependencies = ["pytest"]')
    elif change == "added":
        text = MANIFEST
    elif change == "removed-include":
        text = MANIFEST
    elif change == "moved-section":
        # Deleting a safe header reassigns the unchanged include key to project.
        text = MANIFEST + 'include = ["src/shop"]\n'
    elif change == "dotted-version":
        text = "\n".join("project." + line for line in MANIFEST.splitlines()[1:]).replace('"2.0"', '"3.0"') + "\n"
    elif change in ("malformed", "removed"):
        repo.write("pytest.ini", "[pytest]\n")
        text = "[broken" if change == "malformed" else ""
    commit_manifest(repo, text)
    if change == "removed":
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
    commit_manifest(repo, (repo.path / "pyproject.toml").read_text("utf-8") + 'description = "Updated description"\n')
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
    for host in (".codex", ".claude"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "every change triggers the full command unless all changed lines are known-harmless" in guide
        assert "`include`, `exclude` and `force-include`" in guide
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
    commit_manifest(repo, (client / "pyproject.toml").read_text("utf-8") + 'description = "Updated description"\n')
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
    commit_manifest(repo, (repo.path / "pyproject.toml").read_text("utf-8") + 'description = "Updated description"\n')
    result = pick(repo, base, launcher=unsynced_up.tmp / "uvbin/forge")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert (repo.path / "uv.lock").read_bytes() == lock
    check_generated_ci(repo, lock, launcher=unsynced_up.tmp / "uvbin/forge")
