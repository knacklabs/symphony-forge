"""Real commands recover abandoned starts while keeping live workers visible.

Test-audit: existing timing tests do not cover missing locks or reused pids.
Actual OS identities decide liveness; there is no production test seam.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_board_status_and_times import OLD, _board, _fix, _records, _row, client  # noqa: F401

STORY = "FIX-STALE-WORKER-RUNNING"


def live_identity():
    """Observe the test process independently of Forge's identity reader."""
    if os.name == "nt":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, *([ctypes.POINTER(wintypes.FILETIME)] * 4))
        times = [wintypes.FILETIME() for _ in range(4)]
        assert kernel.GetProcessTimes(kernel.GetCurrentProcess(), *(ctypes.byref(t) for t in times))
        started = str((times[0].dwHighDateTime << 32) | times[0].dwLowDateTime)
    else:
        result = subprocess.run(["ps", "-o", "lstart=", "-p", str(os.getpid())],
            env={**os.environ, "TZ": "UTC", "LC_ALL": "C", "LANG": "C"},
            check=True, capture_output=True, text=True)
        started = "UTC " + " ".join(result.stdout.split())
    return {"pid": os.getpid(), "started": started, "command": sys.executable}


@pytest.mark.parametrize("client,evidence", [
    ("new", evidence) for evidence in
    ("missing lock", "dead lock", "reused lock", "dead process", "reused process",
     "other round process", "live process", "live lock")
] + [("adopted-v1.2.2", "missing lock")], indirect=["client"])
def test_2_unfinished_worker_waits_only_while_a_process_or_lock_is_live(
        client, tmp_path, evidence):
    _fix(client, status="working", round=2)
    folder = _records(client, "events.jsonl", [{"event": "run start", "id": "unfinished-work",
        "item": "correct-state", "kind": "work", "round": 2, "at": OLD}])
    identity = live_identity()
    if evidence.startswith("dead"):
        exited = subprocess.Popen([sys.executable, "-c", "pass"])
        try:
            exited.wait(timeout=10)
        finally:
            if exited.poll() is None:
                exited.kill()
                exited.wait(timeout=10)
        identity = {**identity, "pid": exited.pid}
    elif evidence.startswith("reused"):
        identity = {**identity, "started": "UTC Thu Jan 01 00:00:00 1970"}
    if evidence.endswith("lock") and evidence != "missing lock":
        locks = folder / "threads/fix"
        locks.mkdir(parents=True, exist_ok=True)
        (locks / "correct-state.lock").write_text(json.dumps(identity), "utf-8")
    elif evidence.endswith("process"):
        queue = Path(os.environ["APPDATA" if os.name == "nt" else "XDG_CONFIG_HOME"]) / "forge/agent-runs.json"
        queue.parent.mkdir(parents=True, exist_ok=True)
        queue.write_text(json.dumps([{"id": "unfinished-worker", "kind": "work",
            "round": 1 if evidence == "other round process" else 2,
            "repo_root": client.path.resolve().as_posix(), "checkout_root": client.path.resolve().as_posix(),
            "repo_name": client.path.name, "item": "correct-state", "title": "Correct the state",
            "process": identity, "forge": identity, "agent": None, "joined_at": OLD,
            "started_at": OLD, "model": None, "effort": None, "output_path": None,
            "progress": None, "free": False}]), "utf-8")
    alive = evidence.startswith("live")
    data, text, _ = _board(client, tmp_path)
    row = _row(data, "correct-state")
    assert (row["worker"] is not None) == alive
    assert row["activity"]["status"] == ("running" if alive else "idle")
    assert ("Worker running" in text) == alive
    assert row["next"]["command"] == (None if alive else "forge work correct-state")
    if not alive:
        assert "stopped" in row["next"]["line"].lower()
        assert not any(stage["status"] == "running" for stage in row["stages"])
    next_json = client.forge("next", "--json")
    assert next_json.returncode == 0, next_json.stderr
    following = _row(json.loads(next_json.stdout), "correct-state")
    assert following["worker"] == row["worker"]
    assert following["next"] == row["next"]
    next_text = client.forge("next")
    assert next_text.returncode == 0, next_text.stderr
    # The board names the title; text next names the fix. Both report its liveness.
    expected = ("A worker is building The fix correct-state." if alive
                else "The fix correct-state's worker has stopped.")
    assert expected in next_text.stdout
    if not alive:
        assert "Next: forge work correct-state" in next_text.stdout
