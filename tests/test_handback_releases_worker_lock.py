"""Real handback frees the item while its coordinating session stays alive.

Recreating an older release's leftover lock catches admission failures that
successful handback alone misses. No model stub decides the lock's lifecycle.
"""
import json
import re

import pytest

from test_tools_session_hold import Session
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from test_worker_liveness_controls_next_step import live_identity

STORY = "FIX-STALE-WORKER-RUNNING"


@pytest.mark.parametrize("client, leftover", [
    (False, ""), (False, "legacy"), (False, "current"), (True, "legacy"),
], indirect=["client"], ids=["new-handback", "new-legacy-leftover", "new-leftover", "adopted-leftover"])
def test_1_handback_releases_the_lock_of_a_completed_round(client, monkeypatch, tmp_path, leftover):
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    made = client.forge("fix", "start", "Correct spelling", "--done", "Correct spelling", "--kind", "mechanical")
    assert made.returncode == 0, made.stdout + made.stderr
    host = Session(client, tmp_path / "host", "claude-session")
    try:
        given = host.forge("work", "correct-spelling")
        assert given.returncode == 0, given.stdout + given.stderr
        number = re.search(r"forge handback correct-spelling --round (\d+)", given.stdout)[1]
        lock = client.path / ".git/forge/threads/fix/correct-spelling.lock"
        held = json.loads(lock.read_text("utf-8"))
        busy = host.forge("work", "correct-spelling")
        assert busy.returncode == 1 and "already running" in busy.stderr
        returned = host.forge("handback", "correct-spelling", "--round", number,
                              "--subagent", "builder", "--text", "Done.")
        assert returned.returncode == 0, returned.stdout + returned.stderr
        assert not lock.exists(), "a successful handback must release the item"
        if leftover:
            # A completed round cannot free a different live owner's lock.
            lock.write_text(json.dumps(live_identity()), "utf-8")
            occupied = host.forge("work", "correct-spelling")
            assert occupied.returncode == 1 and "already running" in occupied.stderr
            # Older releases left only the live coordinator identity in the lock.
            if leftover == "legacy":
                held.pop("native_run", None)
            lock.write_text(json.dumps(held), "utf-8")
        again = host.forge("work", "correct-spelling")
        assert again.returncode == 0, again.stdout + again.stderr
        assert "Start a new fixer subagent" in again.stdout or "Continue subagent" in again.stdout
        number = re.search(r"forge handback correct-spelling --round (\d+)", again.stdout)[1]
        ended = host.forge("handback", "correct-spelling", "--round", number,
                           "--subagent", "builder", "--text", "Done.")
        assert ended.returncode == 0, ended.stdout + ended.stderr
    finally:
        host.close()
