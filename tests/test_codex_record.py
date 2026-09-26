"""Codex workers: one forge work per item, and no Codex process left behind it.

forge work and forge doctor run against the stub app-server, whose "hold" status keeps the
conversation from ever starting and outlives its driver, as the server of a crashed call would.
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


def _parent(pid: int) -> int:
    return int(subprocess.run(["ps", "-o", "ppid=", "-p", str(pid)], capture_output=True,
                              text=True, check=True).stdout)


def _held(repo, calls: Path, record: Path) -> tuple[subprocess.Popen, dict]:
    """A forge work on BOARD/PAGE whose app-server holds its conversation from starting, and that
    app-server as recorded."""
    servers = len([call for call in _stub(calls) if "pid" in call])
    work = subprocess.Popen([sys.executable, str(repo.bin / "forge"), "work", "BOARD/PAGE"],
                            cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "hold"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    for _ in range(600):
        try:  # the stub may be halfway through a line
            said = _stub(calls)
        except ValueError:
            said = []
        pids = [call["pid"] for call in said if "pid" in call]
        server = _saved(record).get("app_server") or {}
        if (len(pids) > servers and said[-1].get("method") == "thread/start"
                and server.get("pid") == pids[-1]):
            return work, server
        time.sleep(0.05)
    work.kill()
    pytest.fail(f"forge work never held: {work.communicate()[1]}")


def _crash(work: subprocess.Popen, server: dict) -> None:
    """Kill forge work and its driver together, as a crash would; the app-server stays."""
    driver = _parent(server["pid"])
    os.kill(driver, signal.SIGSTOP)  # so it can't close its client once forge work is gone
    work.kill()
    work.communicate()
    os.kill(driver, signal.SIGKILL)


def test_5_one_worker_per_item(repo, monkeypatch, sdk_data):
    folder, calls = _codex_repo(repo, monkeypatch, sdk_data)
    threads = repo.path / ".git" / "forge" / "threads" / "task" / "BOARD"
    record, lock = threads / "PAGE.json", threads / "PAGE.lock"

    if os.name != "nt":  # no SIGINT to send on Windows
        # The app-server is on record by its id, start time and command before any conversation.
        work, server = _held(repo, calls, record)
        assert _saved(record) == {"app_server": server}
        assert sorted(server) == ["command", "pid", "started"] and "app-server" in server["command"]

        # While it runs, a second forge work on the item refuses and says to wait, from another
        # worktree too, since the lock is in git's shared folder; it commits nothing.
        head = repo.git("rev-parse", "HEAD", cwd=folder)
        busy = repo.forge("work", "BOARD/PAGE", cwd=folder)
        assert busy.stderr == (f"forge work BOARD/PAGE is already running as process {work.pid}, "
                               "and only one runs per item; wait for it to finish.\n"
                               "Next: forge work BOARD/PAGE\n")
        assert repo.git("rev-parse", "HEAD", cwd=folder) == head

        # Ctrl-C lets the lock go, and the app-server with it.
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=30)
        assert not lock.exists() and not _up(server["pid"])

    # The conversation, and HEAD once the turn ends, join the record.
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    saved = _saved(record)
    assert "app-server" in saved["app_server"]["command"]
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

    # While forge work runs, doctor says so and leaves its app-server alone.
    work, server = _held(repo, calls, record)
    assert (f"- forge work BOARD/PAGE is running as process {work.pid}, so doctor leaves its "
            "Codex process alone.\n") in repo.forge("doctor").stdout
    assert _up(server["pid"])

    # An error: the driver dies, and forge work stops the app-server it recorded before it ends.
    os.kill(_parent(server["pid"]), signal.SIGKILL)
    assert "Codex never reported its end" in work.communicate(timeout=30)[1]
    assert not _up(server["pid"])

    # A crash leaves the app-server and a stale lock. Doctor clears the lock, and stops the server
    # only once the record names it: not under another start time.
    work, server = _held(repo, calls, record)
    _crash(work, server)
    saved = _saved(record)
    record.write_text(json.dumps({**saved, "app_server": {**server, "started": "another time"}}),
                      encoding="utf-8")
    assert "Stopped" not in repo.forge("doctor").stdout and _up(server["pid"])
    assert not lock.exists()
    record.write_text(json.dumps(saved), encoding="utf-8")
    assert (f"- Stopped Codex process {server['pid']}, which a crashed forge work BOARD/PAGE "
            "left.\n") in repo.forge("doctor").stdout
    assert not _up(server["pid"])

    # After another crash, the next forge work clears the lock, stops the leftover, and runs.
    work, server = _held(repo, calls, record)
    _crash(work, server)
    assert lock.exists()
    assert repo.forge("work", "BOARD/PAGE").returncode == 0
    assert not _up(server["pid"])
