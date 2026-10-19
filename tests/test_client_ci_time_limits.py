"""Node CI gets thirty minutes; time limits do not request another worker round.

Audit: real init/sync and close commands own these contracts. GitHub and the
reviewer alone are faked. Short cancellations and ordinary failures remain red.
"""
import shutil
from datetime import datetime, timedelta, timezone

import pytest

from conftest import ROOT
from test_close import GREEN, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_land import ITEM, _fix, land  # noqa: F401

STORY = "FIX-NODE-CI-TIMEOUT"


@pytest.mark.parametrize("history", ["new", "upgraded"])
def test_1_node_tests_get_thirty_minutes_on_adoption_and_sync(repo, gh, history):
    repo.write("package.json", '{"scripts":{"test":"node --test"}}\n')
    if history == "new":
        gh.respond("api", stdout="{}")
        done = repo.forge("init")
    else:
        repo.git("switch", "-qc", "fix/upgrade-client")
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt an earlier release")
        done = repo.forge("sync")
    assert done.returncode == 0, done.stdout + done.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0]
    assert "    timeout-minutes: 30\n" in tests_job


@pytest.mark.parametrize("history,conclusion,seconds,name,timeout", [
    ("new", "timed_out", 1800, "tests", True),
    ("new", "cancelled", 1740, "tests (ubuntu-latest)", True),
    ("new", "cancelled", 1860, "tests", True),
    ("new", "cancelled", 1739, "tests", False),
    ("new", "cancelled", 1861, "tests", False),
    ("new", "failure", 1800, "tests", False),
    ("new", "timed_out", 1800, "lint", False),
    ("upgraded", "cancelled", 1800, "tests", True),
    pytest.param("new", "timed_out", 1800, "test group 1 of 1", True, id="generated_group"),
])
def test_2_close_distinguishes_test_time_limits_from_worker_failures(
        land, history, conclusion, seconds, name, timeout):
    env = land
    _client(env, history, "ubuntu-latest")
    where = _fix(env, "working", worked=True, changes={
        "package.json": '{"scripts":{"test":"node --test"}}\n',
        ".github/workflows/forge.yml": (
            "name: Forge\non: pull_request\njobs:\n  tests:\n"
            "    timeout-minutes: 30\n    runs-on: ubuntu-latest\n"
            "    steps:\n      - run: node --test\n"),
    })
    start = datetime(2026, 10, 19, tzinfo=timezone.utc)
    failed = {**run(name, conclusion), "started_at": start.isoformat(),
              "completed_at": (start + timedelta(seconds=seconds)).isoformat()}
    jobs = [job for job in GREEN if job["name"] != name.split(" (")[0]]
    if name.startswith("test group "):
        jobs = [run("tests", "failure"), run("forge-pr-check")]
    env.checks(jobs + [failed])
    done = env.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 1, done.stdout + done.stderr
    if timeout:
        assert "the tests ran out of time after 30 minutes" in done.stderr
        assert "split the suite" in done.stderr
        assert "forge work" not in done.stderr
        assert "Checks failed on the pull request" not in done.stderr
    else:
        assert "Checks failed on the pull request" in done.stderr
        assert f"Next: forge work {ITEM}" in done.stderr
    assert not env.gh_calls("pr", "ready")
