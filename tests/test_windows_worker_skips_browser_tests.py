"""On Windows a builder's own test run skips separate browser-test steps; every other run keeps them."""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, _install
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_close import env  # noqa: F401
from test_upgrade_command import unsynced_up  # noqa: F401,F811

STORY = "FIX-ON-A-WINDOWS-LAPTOP-A-BUILDER-S-OWN-TEST"
pytestmark = pytest.mark.usefixtures("isolated_codex_home")

PY = f'"{Path(sys.executable).as_posix()}"'
SKIP = ("On Windows this run skips the browser tests (npm run test:e2e). The pull request check, "
        "the final check and the full test run still run them.")
COMMANDS = {
    "fast-test-chain": (f"{PY} unit.py && npm run test:e2e", None),
    "pytest-picker": ("forge test --pytest {base} && npm run test:e2e",
                      f"{PY} -m pytest tests -q && npm run test:e2e"),
    "test-chain": (None, f"{PY} -m pytest tests -q && npm run test:e2e"),
    "combined-script": (None, "npm run ci"),
}


def _setup(repo, client, kind):
    fast, full = COMMANDS[kind]
    # npm is the third-party edge: it records that a script ran; Forge decides which steps reach it.
    _install(repo.bin, "npm", f"#!{sys.executable}\nimport pathlib\npathlib.Path('browser-ran').write_text('x')\n")
    (client / "unit.py").write_text("", "utf-8")
    (client / "tests").mkdir(exist_ok=True)
    (client / "tests/test_one.py").write_text("def test_one():\n    assert True\n", "utf-8")
    scripts = {"test:e2e": "playwright test", "ci": "npm run test:unit && npm run test:e2e"}
    (client / "package.json").write_text(json.dumps({"scripts": scripts}), "utf-8")
    path = client / "forge.toml"
    lines = [line for line in path.read_text("utf-8").splitlines() if not line.startswith(("test =", "fast_test ="))]
    lines.insert(1, "test = " + json.dumps(full or fast))
    if fast and full:
        lines.insert(1, "fast_test = " + json.dumps(fast))
    path.write_text("\n".join(lines) + "\n", "utf-8")
    off = ("-c", f"core.hooksPath={client.parent / 'no-hooks'}")  # fixture setup, not a Forge item
    repo.git("add", "-A", cwd=client)
    repo.git(*off, "commit", "-qm", "Set up tests", cwd=client)
    repo.git(*off, "push", "-q", "origin", "main", cwd=client)


def _check(repo, client, monkeypatch, windows, kind):
    monkeypatch.setenv("FORGE_OS", "nt" if windows else "posix")
    marker = client / "browser-ran"
    skips = windows and kind != "combined-script"
    done = repo.forge("test", cwd=client)
    assert done.returncode == 0, done.stdout + done.stderr
    assert marker.exists() != skips, done.stdout
    assert done.stdout.count(SKIP) == (1 if skips else 0), done.stdout
    marker.unlink(missing_ok=True)
    changed = repo.forge("test", "--change", cwd=client)
    assert changed.returncode == 0, changed.stdout + changed.stderr
    assert marker.exists() and SKIP not in changed.stdout


@pytest.mark.parametrize("adopted", [False, True], ids=["new-repo", "adopted-repo"])
@pytest.mark.parametrize("windows", [True, False], ids=["windows", "other"])
@pytest.mark.parametrize("kind", list(COMMANDS))
def test_3_windows_builder_run_skips_browser_steps_and_nothing_else(
        request, repo, gh, tmp_path, monkeypatch, kind, windows, adopted):
    if adopted:
        if kind != "fast-test-chain":
            pytest.skip("one adopted-repo case; the other kinds repeat the new-repo path")
        up = request.getfixturevalue("unsynced_up")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
        repo, client = up.repo, up.repo.path
    else:
        client = _new_repo(repo, gh, tmp_path)
        assert repo.forge("init", "--actions", "yes", cwd=client).returncode == 0
    _setup(repo, client, kind)
    _check(repo, client, monkeypatch, windows, kind)
