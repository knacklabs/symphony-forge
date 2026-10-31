"""Waiters share GitHub reads across commands and worktrees for one minute.

Audit: repeated pending waits previously made independent remote reads. Existing
wait tests cover progress within one process, not reuse by another process.
Only GitHub is faked; the commands, worktrees, and cache are real. No new seam.
"""
from test_close import env  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import client  # noqa: F401
from test_land import ITEM, RUNS, _fix
from test_land_waits_for_check_progress import _pending

STORY = "many-land-runs-each-poll-github-for-chec"


def test_waiters_share_one_status_read_per_minute(client, monkeypatch):
    env, _, _ = client
    _fix(env, "working", worked=True)
    env.checks(_pending(1))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    for instant, expected in [("2026-10-31T00:00:00+00:00", 1),
                              ("2026-10-31T00:00:59+00:00", 1),
                              ("2026-10-31T00:01:00+00:00", 2)]:
        monkeypatch.setenv("FORGE_NOW", instant)
        done = env.repo.forge("land", ITEM)
        assert done.returncode == 1, done.stdout + done.stderr
        assert "tests is still running" in done.stderr
        assert len(env.gh_calls(*RUNS)) == expected
