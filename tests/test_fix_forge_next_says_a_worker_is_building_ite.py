"""`forge next` says a worker is building an item only while its recorded worker process runs."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_story import setup

STORY = "forge-next-says-a-worker-is-building-ite"


def _working_fix(repo):
    setup(repo)
    fix = repo.path.parent / "repo-fix-tidy-up"
    repo.git("worktree", "add", "-q", "-b", "fix/tidy-up", str(fix), "main")
    (fix / ".factory" / "fixes").mkdir(parents=True)
    (fix / ".factory" / "fixes" / "tidy-up.json").write_text(
        json.dumps({"branch": "fix/tidy-up", "status": "working"}), encoding="utf-8")


def _record_worker(repo, proc):
    """Record `proc` as the fix's worker, the way forge work holds its item's lock."""
    def ps(field):
        return subprocess.run(["ps", "-ww", "-o", f"{field}=", "-p", str(proc.pid)],
                              capture_output=True, text=True).stdout.strip()
    started, command = (" ".join(ps("lstart").split()), ps("command")) if os.name != "nt" else ("", "")
    lock = repo.path / ".git" / "forge" / "threads" / "fix" / "tidy-up.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text(json.dumps({"pid": proc.pid, "started": started, "command": command}),
                    encoding="utf-8")


def test_1_next_says_building_only_while_the_recorded_worker_runs(repo):
    _working_fix(repo)
    proc = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                            stdin=subprocess.PIPE)
    try:
        _record_worker(repo, proc)
        # ponytail: Windows records a start time the test can't read, so it checks only the end there.
        if os.name != "nt":
            running = repo.forge("next")
            assert running.returncode == 0, running.stderr
            assert ("A worker is building The fix tidy-up.\n"
                    "Next: wait for it to finish, then forge close tidy-up" in running.stdout), running.stdout
    finally:
        proc.communicate(b"")  # the worker ends; its record stays, as after a crash

    stopped = repo.forge("next")

    assert stopped.returncode == 0, stopped.stderr
    assert "A worker is building" not in stopped.stdout
    assert ("The fix tidy-up's worker has stopped.\nNext: forge close tidy-up"
            in stopped.stdout), stopped.stdout
