"""Ctrl-C retains why a CI wait ended, rather than losing its observed state.

Audit: the existing four-outcome test exhausts deadlines. This cancellation reaches
the real command's SIGINT handler after two simulated minutes of CI polling. Only
GitHub and elapsed time are faked; no production seam or sleeping child is needed.
"""
import pytest

from test_close import GREEN, body, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_item_time_history import records, row
from test_land import ITEM, RUNS, _agent, _fix, _queue, _runs, land  # noqa: F401
from test_land_waits_for_check_progress import clock  # noqa: F401

STORY = "FIX-WHERE-TIME-WENT"


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("command", ["close", "merge"])
@pytest.mark.parametrize("status,phase", [("queued", "queued"), ("in_progress", "running")])
def test_27_cancelled_ci_wait_keeps_observed_phase_reason_and_published_history(
        clock, monkeypatch, history, command, status, phase):
    env = clock
    _agent(env)
    _client(env, history, "ubuntu-latest")
    _fix(env, "working", worked=True, round=1)
    if command == "merge":
        ready = env.close(ITEM)
        assert ready.returncode == 0, ready.stdout + ready.stderr

    marker = env.tmp / "cancel-ci"
    # The mergeability query follows the check lookup and its state classification.
    # It arms the clock only inside CI waiting, after the last GitHub child exits.
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text("utf-8").replace(
        'if args[:2] == ["pr", "view"]:',
        'if args[:2] == ["pr", "view"] and "--json" in args and '
        '"mergeable" in args[args.index("--json") + 1]:\n'
        f'    pathlib.Path({str(marker)!r}).touch()\n'
        'if args[:2] == ["pr", "view"]:'), encoding="utf-8")
    timer = env.tmp / "clock/sitecustomize.py"
    timer.write_text(timer.read_text("utf-8") +
        "\nimport signal\nfrom pathlib import Path\n"
        f"marker = Path({str(marker)!r})\n"
        "advance = time.sleep\n"
        "def cancel(seconds):\n"
        "    advance(seconds)\n"
        "    if marker.exists() and elapsed >= 120:\n"
        "        marker.unlink()\n"
        "        signal.raise_signal(signal.SIGINT)\n"
        "time.sleep = cancel\n", encoding="utf-8")
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    _queue(env, RUNS, *_runs([run("tests", None, status), run("forge-pr-check")]))

    cancelled = env.repo.forge(command, ITEM)

    assert cancelled.returncode == 130, cancelled.stdout + cancelled.stderr
    assert "Traceback" not in cancelled.stderr
    assert len(env.gh_calls(*RUNS)) >= 8  # Two minutes observed, not a deadline exhaustion.
    result = [event for event in records(env.repo, "events.jsonl")
              if event["event"] == "CI result"][-1]
    assert result["outcome"] == "gave_up_" + phase
    assert "Ctrl-C" in result["reason"]
    assert [record for record in records(env.repo, "timings.jsonl")
            if record["step"] == "CI wait"][-1]["outcome"] == "gave_up_" + phase
    assert f"gave up {phase}" in row(env.repo, ITEM)["rounds"][-1]["line"]
    assert not env.gh_calls("pr", "merge")
    if command == "close":
        assert f"CI gave up {phase}" in body(env.gh_calls("pr", "edit")[-1])
    # Merge does not publish on interruption; the ordinary retry refreshes the PR
    # from retained history and must not overwrite the cancellation with green CI.
    (env.repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
    env.checks(GREEN)
    resumed = env.close(ITEM)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert f"gave up {phase}, then passed" in body(env.gh_calls("pr", "edit")[-1])
