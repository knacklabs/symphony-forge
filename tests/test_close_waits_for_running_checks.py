"""Close keeps running checks past ten minutes, with a bounded wait.

Audit: protects the command's wait and limit message. The old fixed deadline
fails before GitHub turns green; land coverage does not exercise close's wait.
Only GitHub and elapsed time are faked, with no production test seam.
"""
import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_land import ITEM, RUNS, _fix, _queue, _runs, land  # noqa: F401

STORY = "FIX-CLOSE-WAITS-RUNNING-CHECKS"


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("fake_clock", [600], indirect=True)
def test_1_close_waits_for_running_checks_until_green_or_the_limit(
        land, fake_clock, monkeypatch, history):
    env = land
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    _client(env, history, "ubuntu-latest")
    where = _fix(env, "working", worked=True)
    running = [run("tests", None, "in_progress"), run("forge-pr-check")]
    _queue(env, RUNS, *_runs(*([running] * 5), GREEN))
    done = env.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean review and green checks" in done.stdout

    (env.repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
    _queue(env, RUNS, *_runs(running))
    done = env.repo.forge("close", ITEM, cwd=where)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "90 minutes limit" in output
    assert "still running" in output
    assert f"forge close {ITEM}" in output

    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    done = env.repo.forge("close", ITEM, cwd=where)
    assert done.returncode == 1, done.stdout + done.stderr
    assert "still running" in done.stderr
