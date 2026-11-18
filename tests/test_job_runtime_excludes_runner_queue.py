"""Audit: close must use job runtime, not check age, to classify cancellation.

The near-limit check age triggers the old false timeout. The long queue case
keeps the reported client scenario. Only GitHub is faked, with no new seam.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import env, run  # noqa: F401
from test_land import ITEM, _fix, land  # noqa: F401

STORY = "FIX-LONG-CI-QUEUES"


@pytest.mark.parametrize("queue_minutes,run_minutes", [(50, 10), (70, 10), (70, 60), (70, None)])
def test_2_close_excludes_runner_queue_from_test_time_limit(land, queue_minutes, run_minutes):
    env = land
    where = _fix(env, "working", worked=True, changes={
        ".github/workflows/forge.yml": "name: Forge\non: pull_request\njobs:\n"
        "  tests:\n    timeout-minutes: 60\n    runs-on: ubuntu-latest\n"
        "    steps:\n      - run: npm test\n",
    })
    queued_at = datetime(2026, 11, 18, tzinfo=timezone.utc)
    started_at = queued_at + timedelta(minutes=queue_minutes)
    completed_at = started_at + timedelta(minutes=run_minutes or 0)
    env.checks([run("forge-pr-check"), {
        **run("tests", "cancelled"), "started_at": queued_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "details_url": "https://github.com/acme/shop/actions/runs/101/job/701",
    }])
    env.gh.respond("api", "--paginate", "--jq", "[.][]",
                   "repos/{owner}/{repo}/actions/jobs/701", stdout=json.dumps({
                       "started_at": started_at.isoformat() if run_minutes is not None else None,
                       "completed_at": completed_at.isoformat(),
                   }))

    done = env.repo.forge("close", ITEM, cwd=where)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    if run_minutes == 60:
        assert "the tests ran out of time after 60 minutes" in output, output
        assert "Next: rerun the tests job, or split the suite" in output, output
        return
    assert "the tests ran out of time" not in output, output
    assert "Checks failed on the pull request: tests" in output, output
    assert f"Next: forge work {ITEM}" in output, output
