"""Nightly tests use the configured test machine.

Test-audit gate:
1. Protect nightly runner selection and read-only tokens after init and sync.
2. Ignoring configured labels sends tests to the wrong machine. A status-write token
   on a persistent test machine lets earlier untrusted code forge review results.
3. PR-machine coverage does not check configured init, custom fallback or nightly permissions.
4. Invoke real commands and read their workflow; no production seam is needed.
"""
import json

import pytest

from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_testplace_workflow import _jobs

STORY = "FIX-FULL-SUITE-ON-TEST-RUNNER"


@pytest.mark.parametrize("runner,test_runner", [
    ("ubuntu-24.04", "fast-tests"),
    ("ubuntu-24.04", "windows-latest"),
    ("custom-runner", None),
    ("ubuntu-24.04", None),
])
def test_1_nightly_tests_use_test_runner_with_runner_as_fallback(repo, gh, tmp_path, runner, test_runner):
    version = repo.forge("--version").stdout.split()[-1]
    config = (f'version = {json.dumps(version)}\nrunner = {json.dumps(runner)}\n'
              'test = "pytest tests -q"\nchecks = ["tests", "forge-pr-check"]\n')
    if test_runner:
        config += f'test_runner = {json.dumps(test_runner)}\n'
    client = _new_repo(repo, gh, tmp_path, config)
    initialized = repo.forge("init", "--actions", "yes", cwd=client)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    workflow = client / ".github/workflows/forge.yml"
    repo.git("checkout", "-qb", "fix/nightly-machines", cwd=client)
    for command in ("init", "sync"):
        if command == "sync":
            synced = repo.forge("sync", cwd=client)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        jobs = _jobs(workflow.read_text("utf-8"))
        assert f'    runs-on: {json.dumps(test_runner or runner)}\n' in jobs["full-suite"], command
        assert "statuses: write" not in jobs["full-suite"], command
        assert f'    runs-on: {json.dumps(runner)}\n' in jobs["full-suite-result"], command
        assert "statuses: write" in jobs["full-suite-result"], command
