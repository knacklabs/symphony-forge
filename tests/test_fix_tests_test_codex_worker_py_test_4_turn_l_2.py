"""test_4_turn_log on Windows, where a gone process's id soon passes to another process.

The test took any process with a reported app-server's id for that app-server, so a later process
given the id failed it now and then. It now counts only a process that started no later than the
stub. Twenty rounds on Windows, run side by side, stand in for twenty CI runs.
"""
from __future__ import annotations

import os

import pytest

from test_codex_worker import sdk_data, test_4_turn_log  # noqa: F401 (a fixture)

STORY = "tests-test-codex-worker-py-test-4-turn-l-2"


@pytest.mark.parametrize("round", range(20 if os.name == "nt" else 1))
def test_1_test_4_turn_log_passes_20_times_in_a_row_on_windows(repo, monkeypatch, sdk_data, round):
    test_4_turn_log(repo, monkeypatch, sdk_data)
