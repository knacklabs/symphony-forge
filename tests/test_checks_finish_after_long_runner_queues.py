"""Audit: real commands protect long waits; only GitHub and time are faked.

Old tests expect a deadline or cover short waits. No production seam is needed.
"""
import pytest
import re

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_ci_waits_for_busy_runners import _client

STORY = "FIX-LONG-CI-QUEUES"


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("fake_clock", [150], indirect=True)
def test_1_active_checks_finish_after_long_queue(land, fake_clock, monkeypatch, command):
    env = land
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    _client(env, "new", "ubuntu-latest")
    if command == "merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    if command == "merge":
        closed = env.repo.forge("close", ITEM, cwd=where)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    queued = [run("tests", None, "queued"), run("forge-pr-check")]
    running = [run("tests", None, "in_progress"), run("forge-pr-check")]
    _queue(env, RUNS, *_runs(*([queued] * 49), *([running] * 41), GREEN))
    done = env.repo.forge(command, ITEM, cwd=where)
    output = done.stdout + done.stderr
    assert done.returncode == 0, output
    assert "Next: forge close" not in output, output
    assert "Waiting:" in output, output
    minutes = [int(value) for value in re.findall(r"checks queued for (\d+) minutes", output)]
    assert all(after - before >= 5 for before, after in zip(minutes, minutes[1:])), output
    assert not env.gh_calls("run", "rerun")
