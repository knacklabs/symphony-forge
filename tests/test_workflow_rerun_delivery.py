"""The pane discards queued failures when their workflow starts again."""
import pytest

from test_close import env  # noqa: F401
from test_mod_plugin import (packaged_mod,  # noqa: F401
                             packaged_events_start_each_sessions_turn_from_real_worker_occurrences)

STORY = "FIX-PANE-CI-RERUN"


@pytest.mark.parametrize("status", ["QUEUED", "IN_PROGRESS"])
def test_1_workflow_rerun_drops_pending_failure(env, packaged_mod, tmp_path, status):
    # Real commands and the packaged mod own the result; only external services are fake.
    # A failure queues during a busy turn, then a rerun starts before delivery.
    packaged_events_start_each_sessions_turn_from_real_worker_occurrences(
        env, packaged_mod, tmp_path, f"workflow {status}")
