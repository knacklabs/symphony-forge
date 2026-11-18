"""Failed test jobs get one workflow retry at the command boundary.

Audit: protects close/merge recovery and the shared attempt limit. Existing
cancelled-run tests never supply failed groups. Only GitHub and time are fake;
the command must request the retry and wait for later check results. No seam.
"""
import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_close_reruns_cancelled_ci import OTHER, RUN_LIST, _check, _workflow
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-RERUN-FAILED-GROUP"


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("failure", ["failure", "timed_out"])
@pytest.mark.parametrize("second", ["success", "failure", "timed_out", "cancelled"])
def test_1_failed_test_jobs_retry_once_and_wait(clock, monkeypatch, command, failure, second):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    _fix(clock, "working", worked=True)
    if command == "merge":
        clock.checks(GREEN)
        closed = clock.repo.forge("close", ITEM)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    failed = [_check("test group 1 of 2", failure),
              _check("test group 2 of 2", "success"), _check("tests", "failure"), OTHER]
    final = GREEN if second == "success" else [
        _check("test group 1 of 2", second), _check("tests", "failure"), OTHER]
    _queue(clock, RUNS, *_runs(failed, final))
    _queue(clock, RUN_LIST, _workflow(5, 77, failure), _workflow(5, 77, second, attempt=2))
    clock.gh.respond("run", "rerun")
    clock.gh.respond("run", "view", stdout='{"attempt": 2}')

    done = clock.repo.forge(command, ITEM)

    assert clock.gh_calls("run", "rerun") == [["run", "rerun", "77", "--failed"]], done.stdout + done.stderr
    assert "Started the failed test jobs again once; waiting for them." in done.stdout
    if second == "success":
        assert done.returncode == 0, done.stdout + done.stderr
    else:
        assert done.returncode == 1, done.stdout + done.stderr
        assert f"forge work {ITEM}" in done.stderr
        assert "Checks failed on the pull request" in done.stderr


@pytest.mark.parametrize("stop", ["lint", "second-attempt", "cancelled-first"])
def test_2_other_failures_and_used_attempts_do_not_restart_ci(clock, monkeypatch, stop):
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _agent(clock)
    _fix(clock, "working", worked=True)
    clock.gh.respond("run", "rerun")
    clock.gh.respond("run", "view", stdout='{"attempt": 2}')
    failed = [_check("test group 1 of 2", "timed_out"), _check("tests", "failure"), OTHER]
    if stop == "lint":
        failed.append(_check("lint", "failure", 8))
    if stop == "cancelled-first":
        _queue(clock, RUNS, *_runs([_check("tests", "cancelled"), OTHER], failed))
        _queue(clock, RUN_LIST, _workflow(5, 77), _workflow(5, 77, "failure", attempt=2))
    else:
        _queue(clock, RUNS, *_runs(failed))
        _queue(clock, RUN_LIST, _workflow(5, 77, "failure", attempt=2 if stop == "second-attempt" else 1))

    done = clock.repo.forge("close", ITEM)

    expected = [["run", "rerun", "77"]] if stop == "cancelled-first" else []
    assert clock.gh_calls("run", "rerun") == expected, done.stdout + done.stderr
    assert done.returncode == 1, done.stdout + done.stderr
    assert f"Next: forge work {ITEM}" in done.stderr
