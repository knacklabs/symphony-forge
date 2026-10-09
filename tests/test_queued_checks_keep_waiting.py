"""Command proof: queues cannot identify a missing shared runner.

Audit: old age and timeout refusals fail real commands; only GitHub and time
are faked. Existing coverage waits only a few polls, inside the wait deadline.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401
from test_ci_waits_for_busy_runners import ACTIONS, JOBS, _client

STORY = "FIX-QUEUED-NOT-STOP"


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("command", ["close", "land", "land-merge"])
def test_1_long_shared_pool_queue_keeps_waiting_then_passes(clock, history, command):
    env = clock
    _client(env, history, "self-hosted")
    if command == "land-merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    queued = [run("tests", None, "queued"), run("forge-pr-check")]
    # Fifteen minutes without activity in this repo: other repos own the pool.
    looks = [queued] * 61 + [GREEN]
    if command == "land-merge":
        looks.insert(0, GREEN)
    _queue(env, RUNS, *_runs(*looks))
    done = env.repo.forge("land" if command == "land-merge" else command, ITEM,
                          cwd=env.repo.path if command == "land-merge" else where)
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "clean review and green checks" in output, output
    assert len(env.gh_calls(*RUNS)) >= len(looks), output
    assert "queued for 15 minutes" in output, output
    assert "shared runners may be busy" in output, output
    assert "no runner may match" in output and "runner setting" in output, output
    assert "no runner has picked" not in output, output


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("lifecycle,activity", [
    ("short", "none"), ("expired", "none"), ("cancelled", "none"), ("rerun", "none"),
    ("rerun", "recent"), ("rerun", "old-running"), ("rerun", "old-completed"),
    ("rerun", "wrong-demand"), ("rerun", "assigned-demand"),
    ("rerun", "wrong-current"), ("dormant", "none")])
def test_2_only_doctor_reports_likely_missing_runner_after_days(clock, history, lifecycle, activity):
    env = clock
    _client(env, history, "self-hosted")
    where = _fix(env, "working", worked=True)
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    now = datetime.now(timezone.utc)
    # GitHub expires unmatched jobs after 24h. Retrying updates the run and queues
    # a new attempt; filter=all still exposes the original expired, unassigned job.
    created = now - (timedelta(minutes=6) if lifecycle == "short" else timedelta(days=8, hours=1))
    expired_at = created + timedelta(days=1)
    original = {"status": "completed", "conclusion": "failure", "labels": ["self-hosted"],
                "runner_id": 0, "started_at": None, "completed_at": expired_at.isoformat()}
    if lifecycle == "cancelled":
        original["conclusion"] = "cancelled"
    queued = {"status": "queued", "conclusion": None, "labels": ["self-hosted"],
              "runner_id": 0, "started_at": None, "completed_at": None}
    retry = lifecycle == "rerun"
    rows = [{"id": 101, "status": "queued" if retry or lifecycle == "short" else "completed",
             "head_sha": head, "created_at": created.isoformat(), "run_attempt": 2 if retry else 1,
             "updated_at": now.isoformat() if retry else expired_at.isoformat()},
            {"id": 102, "status": "completed", "head_sha": "0" * 40,
             "created_at": (now - timedelta(days=8)).isoformat(), "updated_at": now.isoformat()}]
    demand = [queued] if lifecycle == "short" else [original, queued] if retry else [original]
    if activity == "wrong-demand":
        original["labels"] = ["other"]
    elif activity == "assigned-demand":
        original.update(runner_id=7, started_at=(expired_at - timedelta(minutes=5)).isoformat())
    elif activity == "wrong-current":
        rows[0]["head_sha"] = "0" * 40
    elif lifecycle == "dormant":
        # Old demand on another head alone must not diagnose the current PR.
        rows[0]["head_sha"] = "0" * 40
    jobs = [] if activity in ("none", "wrong-demand", "assigned-demand", "wrong-current") else [{
        "labels": ["SELF-HOSTED"], "runner_id": 7, "status": "completed",
        "started_at": (now - timedelta(days=2)).isoformat()}]
    if activity.startswith("old-"):
        # A job starting before the window can still have run inside it.
        jobs[0]["started_at"] = (now - timedelta(days=8)).isoformat()
        if activity == "old-running":
            jobs[0]["status"] = "in_progress"
            rows[1]["status"] = "in_progress"
        else:
            jobs[0]["completed_at"] = (now - timedelta(days=2)).isoformat()
    _queue(env, ACTIONS, *_runs(rows))
    _queue(env, JOBS + ["repos/{owner}/{repo}/actions/runs/101/jobs?filter=all"], *_runs(demand))
    _queue(env, JOBS + ["repos/{owner}/{repo}/actions/runs/102/jobs?filter=all"], *_runs(jobs))
    env.gh.respond("pr", "list", stdout=json.dumps([
        {"state": "OPEN", "headRefOid": head}]))
    done = env.repo.forge("doctor", cwd=where)
    output = done.stdout + done.stderr
    if lifecycle in ("expired", "cancelled", "rerun") and activity == "none":
        assert "likely missing runner" in output, output
        assert "last seven days" in output, output
        assert 'runner = "self-hosted"' in output, output
        assert "only if you change the runner setting" in output, output
    else:
        assert "likely missing runner" not in output, output
