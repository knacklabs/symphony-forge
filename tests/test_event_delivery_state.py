"""Queued pane events use current command-produced state at delivery."""
import pytest

from test_close import env  # noqa: F401
from test_mod_plugin import (packaged_mod,  # noqa: F401
                             packaged_events_start_each_sessions_turn_from_real_worker_occurrences)

STORY = "FIX-FRESH-PANE-EVENTS"


@pytest.mark.parametrize("case", ["fresh advice", "merged before delivery"])
def test_1_delayed_events_follow_current_state(env, packaged_mod, tmp_path, case):
    # The shared host runs the packaged entry point and real Forge commands.
    # Only Claude, its worker, review and GitHub are fake boundaries.
    packaged_events_start_each_sessions_turn_from_real_worker_occurrences(
        env, packaged_mod, tmp_path, case)
