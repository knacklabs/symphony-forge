"""No test leaves a process behind: each test's cleanup ends what it started, stopped or not, and
the run fails naming the test that left one."""
from __future__ import annotations

import os
import signal
import subprocess
import sys
from pathlib import Path

import pytest

from test_codex_record import _up

STORY = "forge-s-own-test-suite-leaves-stopped-co"
TESTS = Path(__file__).resolve().parent

# Three tests that leave a process they started: two stop it first (one passes, one fails after),
# and one leaves it running.
LEAKY = """import os, signal, subprocess, sys

def _left(name, stop=True):
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"],
                            start_new_session=True)
    if stop:
        os.kill(proc.pid, signal.SIGSTOP)
    with open({pids!r}, "a") as pids:
        pids.write(f"{{name}} {{proc.pid}}\\n")

def test_leaves_a_stopped_process():
    _left("passes")

def test_fails_with_a_stopped_process():
    _left("fails")
    assert False, "the test's own failure"

def test_leaves_a_running_process():
    _left("runs", stop=False)
"""


@pytest.mark.skipif(os.name == "nt", reason="the check reads processes with ps, which Windows lacks")
def test_1_a_test_that_leaves_a_process_fails_the_run_by_name(tmp_path):
    pids = tmp_path / "pids.txt"
    leaky = tmp_path / "leaky" / "test_leaky.py"
    leaky.parent.mkdir()
    leaky.write_text(LEAKY.format(pids=str(pids)), encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", str(leaky), "-p", "conftest",
                              "-p", "no:cacheprovider", "-q", "-o", "addopts="],
                             cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(TESTS)},
                             capture_output=True, text=True, timeout=120)
        started = dict(line.split() for line in pids.read_text("utf-8").splitlines())

        assert run.returncode != 0
        assert "ERROR at teardown of test_leaves_a_stopped_process" in run.stdout, run.stdout
        assert f"test_leaves_a_stopped_process left processes running: {started['passes']} " in run.stdout
        assert f"test_fails_with_a_stopped_process left processes running: {started['fails']} " in run.stdout
        assert "ERROR at teardown of test_leaves_a_running_process" in run.stdout, run.stdout
        assert f"test_leaves_a_running_process left processes running: {started['runs']} " in run.stdout
        assert "the test's own failure" in run.stdout
        assert not any(_up(int(pid)) for pid in started.values())
    finally:  # the outer check looks for this test's temp folder, which these children lack
        listed = pids.read_text("utf-8").split() if pids.exists() else []
        for pid in listed[1::2]:
            try:
                os.kill(int(pid), signal.SIGKILL)
            except ProcessLookupError:
                pass


# A test that starts a process, then kills its own worker, so its cleanup never runs.
CRASHY = """import os, signal, subprocess, sys

def test_crashes_its_worker():
    proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"],
                            start_new_session=True)
    with open({pids!r}, "w") as pids:
        pids.write(str(proc.pid))
    os.kill(os.getpid(), signal.SIGKILL)
"""


@pytest.mark.skipif(os.name == "nt", reason="the check reads processes with ps, which Windows lacks")
def test_2_a_crashed_worker_s_process_fails_the_run_by_name(tmp_path):
    pids = tmp_path / "pids.txt"
    crashy = tmp_path / "crashy" / "test_crashy.py"
    crashy.parent.mkdir()
    crashy.write_text(CRASHY.format(pids=str(pids)), encoding="utf-8")
    try:
        run = subprocess.run([sys.executable, "-m", "pytest", str(crashy), "-p", "conftest",
                              "-p", "no:cacheprovider", "-q", "-o", "addopts=", "-n", "1",
                              "--basetemp", str(tmp_path / "base")],
                             cwd=tmp_path, env={**os.environ, "PYTHONPATH": str(TESTS)},
                             capture_output=True, text=True, timeout=120)
        pid = pids.read_text("utf-8")

        assert run.returncode != 0
        assert "crashed while running 'crashy/test_crashy.py::test_crashes_its_worker'" in run.stdout
        assert f"test_crashes_its_worker0 left processes running: {pid} " in run.stdout, run.stdout
        assert not _up(int(pid))
    finally:  # the outer check looks for this test's temp folder, which this child lacks
        if pids.exists():
            try:
                os.kill(int(pids.read_text("utf-8")), signal.SIGKILL)
            except ProcessLookupError:
                pass
