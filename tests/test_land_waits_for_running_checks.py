"""Land waits for checks to finish, with a no-progress limit for missing checks.

Audit: exercise finite running and queued checks across new and upgraded repos,
plus the no-progress limit when GitHub has not reported checks. Fake only GitHub
and elapsed time.
"""
import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_ci_waits_for_busy_runners import _client
from test_land import ITEM, RUNS, _fix, _queue, _runs, land  # noqa: F401

STORY = "FIX-LAND-WAITS-FOR-RUNNING-TESTS"


@pytest.mark.parametrize("history", ["new", "upgraded"])
@pytest.mark.parametrize("fake_clock", [600], indirect=True)
def test_1_land_waits_for_running_checks_then_reports_missing_checks(
        land, fake_clock, monkeypatch, history):
    env = land
    monkeypatch.delenv("FORGE_CHECKS_WAIT", raising=False)
    _client(env, history, "ubuntu-latest")
    _fix(env, "working", worked=True)
    running = [run("tests", None, "in_progress"), run("forge-pr-check")]
    # An unchanged running group must count even alongside a queued group.
    mixed = running + [run("test group 2 of 2", None, "queued")]
    _queue(env, RUNS, *_runs(*([running] * 5), mixed, GREEN))
    done = env.repo.forge("land", ITEM)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "clean review and green checks" in done.stdout

    (env.repo.bin / "gh-queues.json").write_text("[]", encoding="utf-8")
    _queue(env, RUNS, *_runs([]))
    done = env.repo.forge("land", ITEM)
    output = done.stdout + done.stderr
    assert done.returncode == 1, output
    assert "no check progress for 30 minutes" in output
    assert "forge-pr-check has not reported" in output
    assert "No decision is needed" in output
    assert "needs you" not in output
