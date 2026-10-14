"""Recorded history bounds abandoned waits without shortening admitted or cancelled waits.

Test-audit: board totals and round times must stop counting an abandoned lane
at the item's next event. Existing history tests cover only matched lane ends.
Plain-text history is the accounting input; only GitHub is faked, and no
production seam supplies the expected durations.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_board_dependency_timelines import _client
from test_close import env  # noqa: F401
from test_item_time_history import row

STORY = "FIX-DEAD-RUN-WAIT-ENDS"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
@pytest.mark.parametrize("status", ["working", "done"])
def test_1_abandoned_line_wait_ends_at_the_next_item_event(env, tmp_path, monkeypatch, history, status):
    _client(env.repo, env.gh, tmp_path, history)
    began = datetime(2026, 1, 1, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    item, _ = env.start_fix(status=status, round=1, steps=[{"step": "start", "at": at(0)}])
    # Old accounting extended unmatched joins through the item end. The next
    # event for this item now bounds them; another item's event cannot do so.
    events = [
        {"event": "lane joined", "lane_id": "abandoned", "at": at(0)},
        {"event": "work phase", "item": "other-item", "phase": "building", "at": at(5)},
        {"event": "work phase", "phase": "building", "at": at(10)},
        {"event": "lane joined", "lane_id": "admitted", "at": at(20)},
        {"event": "work phase", "phase": "building", "at": at(25)},
        {"event": "lane admitted", "lane_id": "admitted", "at": at(40)},
        {"event": "lane joined", "lane_id": "cancelled", "at": at(50)},
        {"event": "work phase", "phase": "building", "at": at(55)},
        {"event": "lane left", "lane_id": "cancelled", "at": at(60)},
        {"event": "lane joined", "lane_id": "abandoned-again", "at": at(70)},
        {"event": "work phase", "phase": "building", "at": at(80)},
        {"event": "item finished", "at": at(100)},
    ]
    env.repo.write(".git/forge/events.jsonl", "".join(
        json.dumps({"item": item, "id": f"event-{index}", "round": 1, **event}) + "\n"
        for index, event in enumerate(events)))
    monkeypatch.setenv("FORGE_NOW", at(100))
    current = row(env.repo, item)
    assert current["total_seconds"] == 100
    assert current["time_breakdown"]["waiting_in_line"] == 50
    assert current["time_breakdown"]["nothing_running"] == 50
    assert current["rounds"][0]["seconds"]["waiting_in_line"] == 50
    assert "in line 50 seconds" in current["rounds"][0]["line"]
