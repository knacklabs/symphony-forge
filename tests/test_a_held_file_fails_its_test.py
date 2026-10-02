"""A test that leaves a process holding a file in its temp folder fails naming that file, on every
platform, and the process is ended, so the folder can be deleted."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

from test_codex_record import _up

STORY = "windows-ci-jobs-keep-failing-with-permis"
TESTS = Path(__file__).resolve().parent

HOLDER = """import subprocess, sys

def test_holds_a_file(tmp_path):
    held = tmp_path / "held.txt"
    held.write_text("")
    holder = subprocess.Popen(
        [sys.executable, "-c", "import sys, time; f = open(sys.argv[1]); print(flush=True); "
         "time.sleep(300)", str(held)], stdout=subprocess.PIPE)
    holder.stdout.readline()  # the file is open
    with open({pid!r}, "w") as pid:
        pid.write(str(holder.pid))
"""


def test_1_a_process_holding_a_file_fails_its_test_naming_it(tmp_path):
    pid = tmp_path / "pid.txt"
    holder = tmp_path / "holder" / "test_holder.py"
    holder.parent.mkdir()
    holder.write_text(HOLDER.format(pid=str(pid)), encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", str(holder), "-p", "conftest",
                              "-p", "no:cacheprovider", "-q", "-o", "addopts=",
                              "--basetemp", str(tmp_path / "base")],
                             cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(TESTS)},
                             capture_output=True, text=True, timeout=120)
        started = pid.read_text("utf-8")

        assert run.returncode != 0
        assert "ERROR at teardown of test_holds_a_file" in run.stdout, run.stdout
        assert "test_holds_a_file left processes running" in run.stdout, run.stdout
        assert f"{started} " in run.stdout, run.stdout
        if os.name == "nt":  # Windows names the held file; elsewhere ps names the process
            assert f"{os.sep}held.txt: {started} " in run.stdout, run.stdout
        assert not _up(int(started))
    finally:
        if pid.exists():
            try:
                os.kill(int(pid.read_text("utf-8")), getattr(signal, "SIGKILL", signal.SIGTERM))
            except OSError:
                pass
