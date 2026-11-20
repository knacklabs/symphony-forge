"""Node CI gets sixty minutes; time limits do not request another worker round.

Audit: real init/sync and close commands own these contracts. GitHub and the
reviewer alone are faked. Short cancellations and ordinary failures remain red.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_land import ITEM, _fix, land  # noqa: F401

STORY = "FIX-NODE-CI-TIMEOUT"


def _node_client(repo, gh, tmp_path):
    # init needs an empty history, unlike the ordinary repo fixture.
    client, remote = tmp_path / "node-client", tmp_path / "node-client.git"
    repo.git("init", "-q", "--bare", "-b", "main", str(remote))
    repo.git("init", "-q", "-b", "main", str(client))
    repo.git("remote", "add", "origin", str(remote), cwd=client)
    repo.path = client
    repo.write("package.json", '{"scripts":{"test":"node --test"}}\n')
    gh.respond("api", stdout="{}")
    return repo.forge("init", "--actions", "yes")


def _tests_job(repo):
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    return workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0]


@pytest.mark.parametrize("history", ["new"])
def test_1_node_tests_get_sixty_minutes_on_adoption_and_sync(repo, gh, tmp_path, history):
    done = _node_client(repo, gh, tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "    timeout-minutes: 60\n" in _tests_job(repo)


def test_4_sync_raises_an_old_test_timeout_to_sixty_minutes(repo, gh, tmp_path):
    done = _node_client(repo, gh, tmp_path)
    assert done.returncode == 0, done.stdout + done.stderr
    repo.git("switch", "-qc", "fix/upgrade-client")
    repo.write(".github/workflows/forge.yml", "name: forge\non: pull_request\njobs:\n"
               "  tests:\n    timeout-minutes: 10\n    runs-on: ubuntu-latest\n"
               "    steps:\n      - run: npm test\n")
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-qm", "Keep a ten minute limit")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert "    timeout-minutes: 60\n" in _tests_job(repo)


@pytest.mark.parametrize("history,conclusion,seconds,name,timeout", [
    ("new", "timed_out", 1800, "tests", True),
    ("new", "cancelled", 1740, "tests (ubuntu-latest)", True),
    ("new", "cancelled", 1860, "tests", True),
    ("new", "cancelled", 1739, "tests", False),
    ("new", "cancelled", 1861, "tests", False),
    ("new", "failure", 1800, "tests", False),
    ("new", "timed_out", 1800, "lint", False),
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
    if conclusion == "cancelled":
        failed["details_url"] = "https://github.com/acme/shop/actions/runs/301/job/701"
        env.gh.respond("api", "--paginate", "--jq", "[.][]",
                       "repos/{owner}/{repo}/actions/jobs/701", stdout=json.dumps({
                           "runner_id": 9, "started_at": start.isoformat(),
                           "completed_at": failed["completed_at"],
                           "steps": [{"name": "Run tests", "status": "completed",
                                      "started_at": start.isoformat()}],
                       }))
    jobs = [job for job in GREEN if job["name"] != name.split(" (")[0]]
    if name.startswith("test group "):
        jobs = [run("tests", "failure"), run("forge-pr-check")]
    env.checks(jobs + [failed])
    done = env.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 1, done.stdout + done.stderr
    if timeout:
        assert ("On the pull request, the tests ran out of time after 30 minutes.\n"
                f"Next: rerun the tests job, or split the suite, then forge close {ITEM}\n") in done.stderr
        assert "forge work" not in done.stderr
        assert "Checks failed on the pull request" not in done.stderr
    else:
        assert "Checks failed on the pull request" in done.stderr
        assert f"Next: forge work {ITEM}" in done.stderr
    assert not env.gh_calls("pr", "ready")


@pytest.mark.parametrize("history,other", [
    ("new", "lint"),
    ("new", "test group 2 of 2"),
    ("new", "tests (windows-latest)"),
    ("new", "tests"),
])
def test_3_independent_failures_keep_worker_recovery_alongside_timeouts(land, history, other):
    # The aggregate tests failure follows the timed-out group. The other failure
    # still needs a worker, so it must win over timeout-only recovery guidance.
    env = land
    _client(env, history, "ubuntu-latest")
    where = _fix(env, "working", worked=True)
    start = datetime(2026, 10, 19, tzinfo=timezone.utc)
    timeout = {**run("test group 1 of 2", "timed_out"),
               "check_suite": {"id": 7},
               "started_at": start.isoformat(),
               "completed_at": (start + timedelta(minutes=30)).isoformat()}
    env.checks([{**run("tests", "failure"), "check_suite": {"id": 7}}, timeout,
                {**run(other, "failure"), "check_suite": {"id": 8}}, run("forge-pr-check")])

    done = env.repo.forge("close", ITEM, cwd=where)

    assert done.returncode == 1, done.stdout + done.stderr
    expected = "tests" if other.startswith("tests (") else other
    assert f"Checks failed on the pull request: {expected}." in done.stderr
    assert f"Next: forge work {ITEM}" in done.stderr
    assert "the tests ran out of time" not in done.stderr
    assert not env.gh_calls("pr", "ready")
