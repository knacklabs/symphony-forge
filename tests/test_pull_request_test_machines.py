"""Pull request test machines are independent of the other CI machines."""
import json
import re
import shutil

import pytest

from conftest import ROOT

STORY = "FIX-TEST-RUNNER-SETTING"


@pytest.mark.parametrize("history,groups,runner,test_runner", [
    ("new", 1, "ubuntu-24.04", "windows-latest"),
    ("new", 3, "ubuntu-24.04", "windows-latest"),
    ("new", 3, "windows-latest", "self-hosted"),
    ("adopted", 3, "self-hosted", None),
])
def test_1_only_pull_request_tests_use_the_optional_machine(repo, history, groups, runner, test_runner):
    if history == "adopted":
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt an earlier release")
    repo.git("checkout", "-qb", "fix/test-machines")
    version = repo.forge("--version").stdout.split()[-1]
    config = (f'version = "{version}"\nrunner = {json.dumps(runner)}\n'
              f'groups = {groups}\ntest = "vitest run --shard={{group}}/{{groups}}"\n'
              'test_place = "ci"\nchecks = ["tests", "forge-pr-check"]\n')
    repo.write("forge.toml", config)
    baseline = repo.forge("sync")
    assert baseline.returncode == 0, baseline.stdout + baseline.stderr
    path = repo.path / ".github/workflows/forge.yml"
    before = path.read_text("utf-8")
    if test_runner:
        repo.write("forge.toml", config + f'test_runner = {json.dumps(test_runner)}\n')
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = path.read_text("utf-8")
    jobs = dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:|\Z)", workflow.split("\njobs:\n", 1)[1], re.M | re.S))
    expected_jobs = {"tests", "forge-pr-check", "full-suite", "full-suite-result"}
    if groups > 1:
        expected_jobs |= {"docs-check", "tests-passed"}
    assert set(jobs) == expected_jobs
    for name, job in jobs.items():
        selected = json.loads(re.search(r"^    runs-on: (.+)$", job, re.M)[1])
        assert selected == ((test_runner or runner) if name == "tests" else runner)
    assert ("Get-Process -Id $PID" in jobs["tests"]) == (test_runner or runner).startswith("windows-")
    if test_runner is None:
        assert workflow == before
