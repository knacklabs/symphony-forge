"""test_4_turn_log on Windows, where a gone process's id soon passes to another process.

The test took any process with a reported app-server's id for that app-server, so a later process
given the id failed it now and then. It now counts only a process that started no later than the
stub. Twenty rounds on Windows, run side by side, stand in for twenty CI runs.
"""
from __future__ import annotations

import os
import subprocess
import time

import pytest

from conftest import _install
from test_codex_worker import (ROOT, _left, _running, _started, _stub, sdk_data,  # noqa: F401
                               test_4_turn_log)

STORY = "tests-test-codex-worker-py-test-4-turn-l-2"


@pytest.mark.parametrize("round", range(20 if os.name == "nt" else 1))
def test_1_test_4_turn_log_passes_20_times_in_a_row_on_windows(repo, monkeypatch, sdk_data, round):
    test_4_turn_log(repo, monkeypatch, sdk_data)


def test_2_a_codex_process_left_running_fails_test_4_turn_log(tmp_path):
    # The stub app-server, started through its launcher as forge work starts it, left running: the
    # check test_4_turn_log makes of each app-server, with the stub's own start time as the cutoff,
    # finds it. A process with that id that started after the cutoff is another one, and once the
    # app-server has ended nothing is found.
    _install(tmp_path, "codex-app-server", (ROOT / "tests/stubs/codex-app-server").read_text("utf-8"))
    calls = tmp_path / "codex-app-server.jsonl"
    launcher = tmp_path / ("codex-app-server.cmd" if os.name == "nt" else "codex-app-server")
    live = subprocess.Popen([str(launcher)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    work_log = tmp_path / "work-BOARD-PAGE.log"
    work_log.write_text(f"Codex conversation\nCodex app-server: process {live.pid}\n", "utf-8")
    try:
        for _ in range(300):
            if _stub(calls):
                break
            time.sleep(0.1)
        cutoff = _stub(calls)[-1]["started"]
        assert _left(work_log, calls)
        assert _running(live.pid, cutoff)
        assert not _running(live.pid, _started(live.pid) - 1)
    finally:
        live.stdin.close()
        live.wait()
    assert not _left(work_log, calls) and not _running(live.pid, cutoff)
