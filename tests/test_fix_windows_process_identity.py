"""Windows process identity through Forge's lock check."""
from __future__ import annotations

import ctypes
import json
import os
import subprocess
import sys

import pytest

from conftest import _install

STORY = "FIX-ON-WINDOWS-FORGE-S-PROCESS-CHECK-CODEX-I"


@pytest.mark.skipif(os.name != "nt", reason="Windows process handles are required")
def test_1_windows_process_identity_is_live_gone_and_not_reused(repo):
    class FileTime(ctypes.Structure):
        _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]

    def started(process):
        created, exited, kernel, user = (FileTime() for _ in range(4))
        assert ctypes.windll.kernel32.GetProcessTimes(
            ctypes.c_void_p(process._handle), ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user))
        return str((created.high << 32) | created.low)

    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\nworkers = "codex"\n')
    lock = repo.path / ".git" / "forge" / "threads" / "task" / "TEST" / "PROCESS.lock"
    lock.parent.mkdir(parents=True)
    powershell_call = repo.path / "powershell-called"
    _install(repo.bin, "powershell", f"#!{sys.executable}\nfrom pathlib import Path\n"
             f"Path({str(powershell_call)!r}).touch()\nraise SystemExit(1)\n")
    process = subprocess.Popen([sys.executable, "-c", "import sys; sys.stdin.read()"],
                               stdin=subprocess.PIPE)
    try:
        record = {"pid": process.pid, "started": started(process), "command": sys.executable}
        lock.write_text(json.dumps(record), encoding="utf-8")
        live = repo.forge("doctor")
        assert f"forge work TEST/PROCESS is running as process {process.pid}" in live.stdout
        assert lock.exists()

        lock.write_text(json.dumps({**record, "started": "0"}), encoding="utf-8")
        reused = repo.forge("doctor")
        assert f"forge work TEST/PROCESS is running as process {process.pid}" not in reused.stdout
        assert not lock.exists()

        lock.write_text(json.dumps(record), encoding="utf-8")
        process.stdin.close()
        process.wait(timeout=10)
        gone = repo.forge("doctor")
        assert f"forge work TEST/PROCESS is running as process {process.pid}" not in gone.stdout
        assert not lock.exists()
        assert not powershell_call.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
