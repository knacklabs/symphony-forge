"""Waiters share GitHub reads across commands and worktrees for one minute.

Audit: repeated pending waits previously made independent remote reads. Existing
wait tests cover progress within one process, not reuse by another process.
Only GitHub and elapsed time are faked; commands, worktrees and cache are real. No new seam.
"""
import json
import os
import subprocess
import sys
import time

import pytest

from test_close import env  # noqa: F401
from test_conflicting_pull_requests_stop_check_waits import client  # noqa: F401
from test_land import BRANCH, ITEM, RUNS, _fix
from test_land_waits_for_check_progress import _pending

STORY = "many-land-runs-each-poll-github-for-chec"


@pytest.mark.platform
def test_1_waiters_share_one_status_read_per_minute(client, monkeypatch):
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

    # Sequential reuse cannot reach contention or a stalled fetch. Stall only
    # GitHub, then run two real commands: neither lock nor refusal is mocked.
    # The stub also ends itself so broken production code cannot hang the test.
    stub = env.repo.bin / "gh"
    stub.write_text(stub.read_text(encoding="utf-8").replace(
        "args = sys.argv[1:]",
        "args = sys.argv[1:]\n"
        "if args[:4] == ['api', '--paginate', '--jq', '.check_runs[]']:\n"
        "    with (here / 'status-read-starts').open('a') as log: log.write('read\\n')\n"
        "    import threading\n"
        "    for _ in range(650):\n"
        "        if (here / 'status-read-release').exists(): break\n"
        "        threading.Event().wait(0.1)\n", 1), encoding="utf-8")
    offset.write_text("120", encoding="utf-8")
    started = env.repo.bin / "status-read-starts"
    output, error = env.tmp / "status-reader.out", env.tmp / "status-reader.err"
    with output.open("wb") as stdout, error.open("wb") as stderr:
        first = subprocess.Popen([sys.executable, str(env.repo.bin / "forge"), "land", ITEM],
                                 cwd=env.repo.path, stdin=subprocess.DEVNULL,
                                 stdout=stdout, stderr=stderr)
        try:
            deadline = time.monotonic() + (90 if os.name == "nt" else 30)
            while not started.exists() and first.poll() is None and time.monotonic() < deadline:
                time.sleep(0.1)
            assert started.exists(), output.read_text("utf-8") + error.read_text("utf-8")
            done = env.repo.forge("land", ITEM, timeout=150 if os.name == "nt" else 30)
            assert done.returncode == 1, done.stdout + done.stderr
            assert "Could not get access to the shared check status" in done.stderr
            assert started.read_text("utf-8") == "read\n"
            first.wait(timeout=90)
        finally:
            (env.repo.bin / "status-read-release").touch()
            if first.poll() is None:
                try:
                    first.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    first.kill()
                    first.wait(timeout=10)
    assert first.returncode == 1, output.read_text("utf-8") + error.read_text("utf-8")
    assert "gh did not answer within 60 seconds" in error.read_text("utf-8")
