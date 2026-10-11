"""Large pytest selections belong to required CI; workers still run their tests."""
import json
import re
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT
from test_close import env, run  # noqa: F401

STORY = "FIX-SKIP-LARGE-LOCAL-TESTS"


@pytest.mark.parametrize("adopted", [False, True], ids=["init", "earlier-adoption"])
@pytest.mark.parametrize("fast", [False, True], ids=["default-picker", "fast-test-picker"])
@pytest.mark.parametrize("checks", ["red", "green", "without-tests"])
@pytest.mark.parametrize("selection", [2, 3, "shared"])
def test_1_close_skips_more_than_a_third_but_required_checks_still_gate(
        env, monkeypatch, adopted, fast, checks, selection):
    # Real pytest writes the receipt; only review and GitHub are faked.
    if adopted:
        version = env.repo.forge("--version").stdout.split()[-1]
        env.repo.git("switch", "-qc", "fix/adopt")
        env.repo.write(".factory/fixes/adopt.json", json.dumps({
            "kind": "fix", "branch": "fix/adopt", "why": "Adopt", "done_when": "Adopted",
            "status": "started"}))
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client",
                        env.repo.path, dirs_exist_ok=True)
        settings = (env.repo.path / "forge.toml").read_text("utf-8")
        env.repo.write("forge.toml", settings.replace('version = "v1.2.2"',
                                                     f'version = "{version}"'))
        synced = env.repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
        env.repo.git("add", "-A")
        env.repo.git("commit", "-qm", "Refresh earlier adoption")
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    monkeypatch.setenv("PYTEST_ADDOPTS", "")
    log = env.tmp / "ran"
    log.mkdir()
    command = subprocess.list2cmdline([sys.executable, "-m", "pytest", "tests", "-q"])
    settings = (env.repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^test = .*\n", "", settings, flags=re.M)
    if checks == "without-tests":
        settings = re.sub(r"^checks = .*", 'checks = ["forge-pr-check"]', settings, flags=re.M)
    settings = "test = " + json.dumps(command) + "\n" + settings
    if fast:
        settings = 'fast_test = "forge test --pytest {base}"\n' + settings
    env.repo.write("forge.toml", settings)
    env.repo.write("conftest.py", "import os, pathlib, pytest\n"
                   "@pytest.fixture(autouse=True)\ndef receipt(request):\n"
                   "    assert 'FORGE_CLOSE_TESTS' not in os.environ\n"
                   f"    (pathlib.Path({json.dumps(log.as_posix())}) / request.node.name).touch()\n")
    for number in range(6):
        env.repo.write(f"tests/test_case_{number}.py",
                       f"def test_case_{number}():\n    assert 1 + 1 == 2\n")
    env.repo.git("add", "-A")
    env.repo.git("commit", "-qm", "Set up real test suite")
    if adopted:  # stands in for the merged pull request that the synced hooks require
        env.repo.git("switch", "-q", "main")
        env.repo.git("merge", "-q", "--ff-only", "fix/adopt")
    env.repo.git("-c", "core.hooksPath=/dev/null", "push", "-q", "origin", "main")
    changes = ({"conftest.py": (env.repo.path / "conftest.py").read_text("utf-8") + "# changed\n"}
               if selection == "shared" else
               {f"tests/test_case_{number}.py":
                f"def test_case_{number}():\n    assert 2 + 2 == 4\n"
                for number in range(selection)})
    item, where = env.start_fix(changes)
    large = selection != 2
    skipped = large and checks != "without-tests"
    failed = skipped and checks == "red"
    env.checks(([run("tests", "failure" if failed else "success")]
                if checks != "without-tests" else []) + [run("forge-pr-check")])
    closed = env.close(item)
    assert closed.returncode == (1 if failed else 0), closed.stdout + closed.stderr
    count = 6 if selection == "shared" or (not fast and checks == "without-tests") else selection
    expected = set() if skipped else {f"test_case_{number}" for number in range(count)}
    assert {path.name for path in log.iterdir()} == expected
    message = "More than a third of the test files selected; skipping local tests and relying on the pull request's required checks."
    assert closed.stdout.count(message) == (1 if skipped else 0), closed.stdout
    if failed:  # the pull request's failed tests check still stops close
        assert "Checks failed on the pull request: tests." in closed.stderr
    else:
        assert "Ready:" in closed.stdout, closed.stdout + closed.stderr
    # Explicit worker runs keep the old contract, even for shared inputs or large selections.
    tested = env.repo.forge("test", cwd=where)
    assert tested.returncode == 0, tested.stdout + tested.stderr
    expected = {f"test_case_{number}" for number in
                range(6 if not fast or selection == "shared" else selection)}
    assert {path.name for path in log.iterdir()} == expected
