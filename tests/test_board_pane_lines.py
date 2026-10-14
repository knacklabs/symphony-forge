"""The pane's Board tab and /forge text open with the board's first-screen lines.

The board JSON contract (tests/fixtures/board.json and the older release's
board-previous.json) is fed to the shipped summary.ts through Node. The grouped layout
itself is proven in tests/test_fix_pane_grouped_board.py; this file adds the five-row
cap and the older-release rule the plan names for the pane.
"""
import copy

import pytest

from test_fix_pane_grouped_board import FIXTURE, PREVIOUS, lines, row


def seven_items_need_you_shows_five_and_n_more(tmp_path):
    board = copy.deepcopy(FIXTURE["board"])
    ready = board["items"][0]
    asks = [row(ready, id=f"fix-{n}", title=f"Fix number {n}", stage="building", state="in progress",
                needs_person=True, next={"command": None, "line": "Answer it.", "step": f"forge work fix-{n}"})
            for n in range(1, 8)]
    board["items"] = asks
    board["team"]["counts"]["fixes"]["in progress"] = 7
    board["team"]["needs_you"] = [{"id": a["id"], "kind": "fix", "title": a["title"], "reason": "worker question",
                                   "since": "2026-10-12T12:00:00+00:00", "waited_seconds": 86400} for a in asks]
    shown = lines(tmp_path, board).splitlines()
    assert shown[0] == "7 in progress · 7 needs you"
    titles = [line.strip() for line in shown if line.strip().startswith("Fix number")]
    assert titles == [f"Fix number {n}" for n in range(1, 6)]
    assert shown[-1] == "  and 2 more · forge board for all"


def an_older_forge_board_draws_rows_and_no_team_line(tmp_path):
    shown = lines(tmp_path, PREVIOUS["board"])
    assert shown.startswith("READY TO MERGE\n  Polish the guide\n"), shown
    assert "in progress" not in shown and "needs you" not in shown


@pytest.mark.parametrize("case", [seven_items_need_you_shows_five_and_n_more,
                                  an_older_forge_board_draws_rows_and_no_team_line])
def test_9_the_pane_opens_with_the_boards_first_screen_lines(tmp_path, case):
    case(tmp_path)
