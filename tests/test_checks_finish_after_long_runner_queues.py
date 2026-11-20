"""Audit: real commands protect long waits; only GitHub and time are faked.

Old tests expect a deadline or cover short waits. No production seam is needed.
"""
import pytest
import re
import json

from conftest import patient

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_ci_waits_for_busy_runners import _client

STORY = "FIX-LONG-CI-QUEUES"


def _watch_progress(tmp_path):
    """Observe actual output at the existing controlled clock, without changing it."""
    clock = tmp_path / "clock" / "sitecustomize.py"
    log = tmp_path / "progress.jsonl"
    observer = '''
import builtins, json
original_print = builtins.print
def observed_print(*args, **kwargs):
    if args and str(args[0]).startswith("Waiting:"):
        with open(PROGRESS_LOG, "a", encoding="utf-8") as output:
            output.write(json.dumps([time.monotonic(), str(args[0])]) + "\\n")
    return original_print(*args, **kwargs)
builtins.print = observed_print
'''.replace("PROGRESS_LOG", json.dumps(log.as_posix()))
    patient(lambda: clock.write_text(clock.read_text("utf-8") + observer, "utf-8"))
    return log


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("fake_clock", [150], indirect=True)
def test_1_active_checks_finish_after_long_queue(land, fake_clock, monkeypatch, command, tmp_path):
    env = land
    progress = _watch_progress(tmp_path)
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
    notices = [json.loads(line) for line in progress.read_text("utf-8").splitlines()]
    assert sum("tests is still running" in line for _, line in notices) >= 2, notices
    assert all(after[0] - before[0] >= 300 for before, after in zip(notices, notices[1:])), notices
    assert not env.gh_calls("run", "rerun")


@pytest.mark.parametrize("command", ["close", "merge", "land"])
@pytest.mark.parametrize("case", ["red-queued", "red-running", "timeout-running", "retry"])
@pytest.mark.parametrize("fake_clock", [600], indirect=True)
def test_3_failed_checks_end_waits_and_retries_keep_waiting(land, fake_clock, monkeypatch, tmp_path, command, case):
    """Audit: a required failure ends the wait; recovery cannot reuse a stale deadline.

    Round six replaces the earlier failed-sibling wait policy. The existing table
    owns that command contract and a retry after ten minutes. Only gh and the
    existing clock are faked; elapsed command time distinguishes the two paths.
    """
    from test_close_reruns_cancelled_ci import _workflow

    env = land
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    _client(env, "new", "ubuntu-latest")
    if command == "merge":
        _agent(env)
    where = _fix(env, "working", worked=True)
    if command == "merge":
        closed = env.repo.forge("close", ITEM, cwd=where)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    running = [run("tests", None, "in_progress"), run("forge-pr-check")]
    if case == "retry":
        cancelled = [{**run("tests", "cancelled"), "check_suite": {"id": 5}}, run("forge-pr-check")]
        _queue(env, RUNS, *_runs(running, running, cancelled, running, GREEN))
        _queue(env, ["api", "--paginate", "--jq", ".workflow_runs[]"], _workflow(5, 77))
        env.gh.respond("run", "rerun")
    else:
        from datetime import datetime, timedelta, timezone
        start = datetime(2026, 11, 18, tzinfo=timezone.utc)
        bad = ({**run("tests (windows-latest)", "timed_out"), "started_at": start.isoformat(),
                "completed_at": (start + timedelta(minutes=60)).isoformat()}
               if case == "timeout-running" else run("tests (windows-latest)", "failure"))
        active = run("tests (ubuntu-latest)", None, "queued" if case == "red-queued" else "in_progress")
        _queue(env, RUNS, *_runs(*([[bad, active, run("forge-pr-check")]] * 3), [bad, *GREEN]))
    elapsed = tmp_path / "clock" / "elapsed"
    before = float(elapsed.read_text("utf-8"))

    done = env.repo.forge(command, ITEM, cwd=where)
    output = done.stdout + done.stderr
    if case == "retry":
        assert float(elapsed.read_text("utf-8")) - before >= 1800, output
        assert done.returncode == 0, output
        assert "Started it again; waiting for it" in output, output
    else:
        assert float(elapsed.read_text("utf-8")) == before, output
        assert done.returncode == 1, output
        assert ("the tests ran out of time" if case == "timeout-running"
                else "Checks failed on the pull request: tests") in output, output
