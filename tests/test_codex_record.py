"""Codex workers: one forge work per item, and no Codex process left behind it.

forge work and forge doctor run against the stub app-server, which can get stuck: "stall" never
answers initialize, so Codex never starts, and "hold" never answers thread/start. Stuck, it ignores
its stdin, as a server left behind by a crash would.
Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from conftest import _install
from test_codex_worker import _codex_repo, _stub, sdk_data  # noqa: F401 (sdk_data is a fixture)

STORY = "FORGE-WARM-1"
# A ps, and on Windows a PowerShell, that can't read any process.
BLIND = "#!/usr/bin/env python3\nimport sys\nsys.exit('stub: no process can be read')\n"


def _saved(path: Path) -> dict:
    return json.loads(path.read_text("utf-8")) if path.exists() else {}


def _up(pid: int) -> bool:
    """Whether the process runs; a finished one its parent hasn't collected yet doesn't."""
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True,
                          text=True).stdout.strip()
    return bool(stat) and not stat.startswith("Z")


def _down(pid: int) -> bool:
    """Whether the process has gone, or goes within ten seconds: stopping takes a moment."""
    for _ in range(100):
        if not _up(pid):
            return True
        time.sleep(0.1)
    return False


def _held(repo, calls: Path, record: Path, status: str) -> tuple[subprocess.Popen, dict, int]:
    """A forge work on BOARD/PAGE whose stub app-server is stuck ("stall" or "hold"). Returns the
    forge work, its record once the stub is stuck, and the stub's process id."""
    stuck = {"stall": "initialize", "hold": "thread/start"}[status]
    servers = len([call for call in _stub(calls) if "pid" in call])
    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                            cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": status},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        try:  # the stub may be halfway through a line
            said = _stub(calls)
        except ValueError:
            said = []
        pids = [call["pid"] for call in said if "pid" in call]
        saved = _saved(record)
        if (len(pids) > servers and said[-1].get("method") == stuck
                and (status == "stall" or (saved.get("app_server") or {}).get("pid") == pids[-1])):
            return work, saved, pids[-1]
        time.sleep(0.05)
    work.kill()
    pytest.fail(f"forge work never got stuck: {work.communicate()[1]}")


def _crash(work: subprocess.Popen, saved: dict) -> None:
    """Kill forge work while its driver can't act, as a crash might: its group is left behind."""
    os.kill(saved["driver"]["pid"], signal.SIGSTOP)
    work.kill()
    work.communicate()


def test_5_one_worker_per_item(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    threads = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD"
    record, lock = threads / "PAGE.json", threads / "PAGE.lock"

    if os.name != "nt":  # no SIGINT to send on Windows
        # The driver is on record by its id, start time and command at once, before Codex has
        # started: here the app-server never answers initialize.
        work, saved, stub = _held(repo, calls, record, "stall")
        driver = saved["driver"]
        assert saved == {"driver": driver, "app_server": None}
        assert sorted(driver) == ["command", "pid", "started"] and "codex_turn" in driver["command"]

        # While it runs, a second forge work on the item refuses and says to wait, from another
        # worktree too, since the lock is in git's shared folder; it commits nothing.
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        busy = repo.forge("work", "BOARD/PAGE", cwd=folder)
        assert busy.stderr == (f"forge work BOARD/PAGE is already running as process {work.pid}, "
                               "and only one runs per item; wait for it to finish.\n"
                               "Next: forge work BOARD/PAGE\n")
        assert repo.git("rev-parse", "HEAD", cwd=folder) == head

        # Ctrl-C lets the lock go, and every process of the call with it.
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=30)
        assert not lock.exists() and _down(stub) and _down(driver["pid"])

    # The app-server, the conversation, and HEAD once the turn ends, join the record.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    saved = _saved(record)
    assert "codex_turn" in saved["driver"]["command"]
    assert (saved["conversation"], saved["head"]) == ("thr-stub-1",
                                                      repo.git("rev-parse", "HEAD", cwd=folder))

    # When Forge can't read who holds the lock, the owner counts as running: forge work refuses,
    # naming the lock.
    lock.write_text(json.dumps({"pid": os.getpid(), "started": "long ago",
                                "command": "forge work BOARD/PAGE"}), encoding="utf-8")
    for tool in ("ps", "powershell"):
        _install(repo.bin, tool, BLIND)
    blind = repo.forge("work", "BOARD/PAGE")
    assert blind.stderr == (f"Forge can't read the start time and command of process {os.getpid()}"
                            f", so it can't tell who holds {lock}; it counts it as held.\n"
                            f"Next: delete {lock} once no forge work runs on BOARD/PAGE\n")

    # Once it can, a lock whose process id now belongs to another process is stale and cleared.
    for fake in [*repo.bin.glob("ps*"), *repo.bin.glob("powershell*")]:
        fake.unlink()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert not lock.exists()


@pytest.mark.skipif(os.name == "nt", reason="the crashes are made with POSIX signals")
def test_6_nothing_left_running(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    threads = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD"
    record, lock = threads / "PAGE.json", threads / "PAGE.lock"

    # Killing forge work while Codex is still starting leaves nothing: the driver sees Forge go
    # and ends its whole process group.
    work, saved, stub = _held(repo, calls, record, "stall")
    work.kill()
    work.communicate()
    assert _down(stub) and _down(saved["driver"]["pid"])

    # Ctrl-C while the driver can't act (stopped, here): forge work still returns, ends the
    # driver's group itself, and lets the lock go.
    work, saved, stub = _held(repo, calls, record, "stall")
    os.kill(saved["driver"]["pid"], signal.SIGSTOP)
    work.send_signal(signal.SIGINT)
    work.communicate(timeout=30)
    assert not lock.exists() and _down(stub) and _down(saved["driver"]["pid"])

    # While forge work runs, doctor says so and leaves it alone. An error: the driver dies, and
    # forge work stops the app-server it recorded before it ends.
    work, saved, stub = _held(repo, calls, record, "hold")
    assert (f"- forge work BOARD/PAGE is running as process {work.pid}, so doctor leaves its "
            "Codex process alone.\n") in repo.forge("doctor").stdout
    assert _up(stub)
    os.kill(saved["driver"]["pid"], signal.SIGKILL)
    assert "Codex never reported its end" in work.communicate(timeout=30)[1]
    assert _down(stub)

    # A crash that leaves the driver unable to act (stopped, here) leaves its process group and a
    # stale lock. Doctor clears the lock, and stops the group only once the record names the
    # driver: not under another start time.
    work, saved, stub = _held(repo, calls, record, "stall")
    _crash(work, saved)
    record.write_text(json.dumps({**saved, "driver": {**saved["driver"], "started": "another"}}),
                      encoding="utf-8")
    assert "Stopped" not in repo.forge("doctor").stdout and _up(stub)
    assert not lock.exists()
    record.write_text(json.dumps(saved), encoding="utf-8")
    assert ("- Stopped the Codex processes that a crashed forge work BOARD/PAGE left.\n"
            in repo.forge("doctor").stdout)
    assert _down(stub) and _down(saved["driver"]["pid"])

    # After another crash, the next forge work stops the leftover group by identity, and runs.
    work, saved, stub = _held(repo, calls, record, "stall")
    _crash(work, saved)
    assert lock.exists()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert _down(stub) and _down(saved["driver"]["pid"])
