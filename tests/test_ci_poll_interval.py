"""CI request spacing at the command boundary.

Audit: a fixed sleep ignores the override. Existing deadline tests do not check
spacing. Reuse the GitHub stub and controlled clock with no production seam.
"""
import pytest

from test_close import GREEN, env, run  # noqa: F401
from test_land import ITEM, RUNS, _fix, _queue, _runs, land  # noqa: F401

STORY = "ci-poll-60s"


@pytest.mark.parametrize("interval", [None, "2.5"])
def test_1_ci_polls_at_the_configured_interval(land, fake_clock, monkeypatch, tmp_path, interval):
    env = land
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "600")
    if interval is None:
        monkeypatch.delenv("FORGE_CHECKS_POLL", raising=False)
    else:
        monkeypatch.setenv("FORGE_CHECKS_POLL", interval)
    _fix(env, "working", worked=True)
    _queue(env, RUNS, *_runs(
        [run("tests", None, "in_progress"), run("forge-pr-check")], GREEN))
    elapsed = tmp_path / "clock" / "elapsed"
    before = float(elapsed.read_text("utf-8"))

    done = env.repo.forge("close", ITEM)

    assert done.returncode == 0, done.stdout + done.stderr
    assert float(elapsed.read_text("utf-8")) - before == (60 if interval is None else 2.5)
