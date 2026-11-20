"""Close counts actual Actions job runtime when it classifies a cancellation.

Behavior: a cancelled test is a timeout only when its runner job ran for the
configured limit. Regression: GitHub can report a queued timestamp as
started_at for runner_id=0, making a job that never ran look like a timeout.
Existing timeout tests use check timestamps or a null job start, so they miss
that valid Actions response. This drives the real close command and fakes only
GitHub; no production seam is needed.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import env, run  # noqa: F401
from test_ci_time_report import _at, _check, _graphql, _pull, _start_fix
from test_land import ITEM, _fix, land  # noqa: F401

STORY = "FIX-LONG-CI-QUEUES"


@pytest.mark.parametrize("queue_minutes,job_start_minutes,job_run_minutes,runner_id,times_out", [
    (50, 50, 10, 9, False),
    (70, 70, 10, 9, False),
    (70, 70, 60, 9, True),
    (70, None, None, 0, False),
    (60, 0, 60, 0, False),
])
def test_2_close_excludes_runner_queue_from_test_time_limit(
        land, queue_minutes, job_start_minutes, job_run_minutes, runner_id, times_out):
    env = land
    where = _fix(env, "working", worked=True, changes={
        ".github/workflows/forge.yml": "name: Forge\non: pull_request\njobs:\n"
        "  tests:\n    timeout-minutes: 60\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: npm test\n",
    })
    queued_at = datetime(2026, 11, 18, tzinfo=timezone.utc)
    job_started_at = (queued_at + timedelta(minutes=job_start_minutes)
                      if job_start_minutes is not None else None)
    completed_at = (job_started_at + timedelta(minutes=job_run_minutes)
                    if job_started_at is not None and job_run_minutes is not None
                    else queued_at + timedelta(minutes=queue_minutes))
    env.checks([run("forge-pr-check"), {
        **run("tests", "cancelled"), "started_at": queued_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "details_url": "https://github.com/acme/shop/actions/runs/101/job/701",
    }])
    env.gh.respond("api", "--paginate", "--jq", "[.][]",
                   "repos/{owner}/{repo}/actions/jobs/701", stdout=json.dumps({
                       "runner_id": runner_id,
                       # An unassigned Actions job can expose the queue timestamp here.
                       "started_at": job_started_at.isoformat() if job_started_at else None,
                       "completed_at": completed_at.isoformat(),
                       "steps": ([{"name": "Run tests", "status": "completed"}]
                                 if runner_id else []),
                   }))

    done = env.repo.forge("close", ITEM, cwd=where)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    if times_out:
        assert "the tests ran out of time after 60 minutes" in output, output
        assert "Next: rerun the tests job, or split the suite" in output, output
        return
    assert "the tests ran out of time" not in output, output
    assert "Checks failed on the pull request: tests" in output, output
    assert f"Next: forge work {ITEM}" in output, output


@pytest.mark.parametrize("queue_minutes,job_run_minutes,runner_id,times_out", [
    (50, 10, 9, False),
    (50, 60, 9, True),
    (60, 60, 0, False),
], ids=["long-queue-short-run", "actual-sixty-minute-run", "never-ran"])
def test_4_ci_report_uses_job_runtime_for_cancelled_tests(
        land, queue_minutes, job_run_minutes, runner_id, times_out):
    env = land
    item, where = _start_fix(env, "queued-cancelled-tests")
    queued_at = _at()
    job_start_minutes = queue_minutes if runner_id else 0
    job_started_at = _at(job_start_minutes)
    completed_at = _at(job_start_minutes + job_run_minutes)
    sha = env.commit(where, ".github/workflows/forge.yml",
                     "name: Forge\non: pull_request\njobs:\n  tests:\n"
                     "    timeout-minutes: 60\n    runs-on: ubuntu-latest\n"
                     "    steps:\n      - run: python -m pytest\n")
    test_check = _check("tests", queued_at, completed_at,
                        conclusion="CANCELLED", run_id=301)
    test_check["detailsUrl"] = "https://github.com/acme/shop/actions/runs/301/job/701"
    pr = _pull(7, [test_check, _check("forge-pr-check", queued_at, completed_at, run_id=301)])
    pr["commits"]["nodes"][-1]["commit"]["oid"] = sha
    _graphql(env, [pr])
    job = {"name": "tests", "runner_id": runner_id,
           "started_at": job_started_at, "completed_at": completed_at,
           "steps": ([{"name": "Run tests", "status": "completed",
                       "started_at": job_started_at}]
                     if runner_id else [])}
    env.gh.respond("api", "--paginate", "--jq", "[.][]",
                   "repos/{owner}/{repo}/actions/jobs/701", stdout=json.dumps(job))
    env.gh.respond("api", "repos/{owner}/{repo}/actions/runs/301/jobs?filter=all&per_page=100",
                   stdout=json.dumps({"jobs": [job]}))
    env.checks([run("forge-pr-check"), {
        **run("tests", "cancelled"), "started_at": queued_at,
        "completed_at": completed_at,
        "details_url": "https://github.com/acme/shop/actions/runs/301/job/701",
    }])

    done = env.repo.forge("close", item, cwd=where)
    output = done.stdout + done.stderr

    assert done.returncode == 1, output
    if times_out:
        assert "the tests ran out of time after 60 minutes" in output, output
        assert "slowest tests (110 min, timed out)" in output, output
    else:
        assert "Checks failed on the pull request: tests" in output, output
        assert "timed out" not in output.lower(), output
