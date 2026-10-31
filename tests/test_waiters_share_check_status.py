"""Waiters share GitHub reads across commands and worktrees for one minute.

Audit: repeated pending waits previously made independent remote reads. Existing
wait tests cover progress within one process, not reuse by another process.
Only GitHub is faked; the commands, worktrees, and cache are real. No new seam.
"""
import json

from test_close import env  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import client  # noqa: F401
from test_land import BRANCH, ITEM, RUNS, _fix
from test_land_waits_for_check_progress import _pending

STORY = "many-land-runs-each-poll-github-for-chec"


def test_waiters_share_one_status_read_per_minute(client, monkeypatch):
    env, sleeps, _ = client
    _fix(env, "working", worked=True)
    env.checks(_pending(1))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    clock = sleeps.parent / "sitecustomize.py"
    offset = sleeps.parent / "status-clock"
    clock.write_text(clock.read_text(encoding="utf-8")
                     + f"time.monotonic = lambda: float(Path({json.dumps(offset.as_posix())}).read_text('utf-8'))\n",
                     encoding="utf-8")
    for elapsed, expected in [(0, 1), (59, 1), (60, 2)]:
        offset.write_text(str(elapsed), encoding="utf-8")
        done = env.repo.forge("land", ITEM)
        assert done.returncode == 1, done.stdout + done.stderr
        assert "tests is still running" in done.stderr
        assert len(env.gh_calls(*RUNS)) == expected
        assert len(env.gh_calls("pr", "view", BRANCH, "--json",
                                "mergeable,headRefOid,number,headRefName")) == expected
