"""test_4_turn_log on Windows, where a gone process's id soon passes to another process.

The test took any process with a reported app-server's id for that app-server, so a later process
given the id failed it now and then. It now counts only a process that started no later than the
stub. Twenty rounds on Windows, run side by side, stand in for twenty CI runs.
"""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_codex_worker import _running, sdk_data, test_4_turn_log  # noqa: F401 (a fixture)

STORY = "tests-test-codex-worker-py-test-4-turn-l-2"


@pytest.mark.parametrize("round", range(20 if os.name == "nt" else 1))
def test_1_test_4_turn_log_passes_20_times_in_a_row_on_windows(repo, monkeypatch, sdk_data, round):
    test_4_turn_log(repo, monkeypatch, sdk_data)


def test_2_a_codex_process_left_running_fails_test_4_turn_log():
    # The check test_4_turn_log makes of each app-server: a live process counts, a finished one
    # doesn't, and on Windows neither does one that started after the stub it is checked against.
    live = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        assert _running(live.pid)
        assert _running(live.pid, 0) is (os.name != "nt")
    finally:
        live.kill()
        live.wait()
    assert not _running(live.pid)
