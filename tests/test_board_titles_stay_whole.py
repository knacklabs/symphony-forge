"""The board keeps a fix's whole title, and finds a story's title on a part's branch."""
import json

from test_board_status_and_times import _board, _fix, _row, client  # noqa: F401
from test_board import DOC

STORY = "FIX-BOARD-TITLES-STAY-WHOLE"
TITLE = "Readers can follow the progress of their improvement without contradictory information everywhere"


def test_1_a_fix_shows_its_whole_title(client, tmp_path):
    _fix(client, TITLE)
    data, _, _ = _board(client, tmp_path)
    assert _row(data, "correct-state")["title"] == TITLE


def test_2_a_story_whose_plan_is_only_on_a_part_branch_shows_the_plan_title(client, tmp_path):
    branch, folder = "task/LOST-ONE", tmp_path / "one-part"
    client.git("worktree", "add", "-q", "-b", branch, str(folder), "main")
    (folder / ".factory/stories/LOST/tasks").mkdir(parents=True)
    (folder / ".factory/stories/LOST/tasks/ONE.json").write_text(
        json.dumps({"status": "working", "branch": branch}), "utf-8")
    (folder / "plans").mkdir(exist_ok=True)
    (folder / "plans/LOST.md").write_text(
        DOC.replace("# Shoppers can save a basket", "# Couriers book slots", 1).replace("| SAVE |", "| ONE |", 1), "utf-8")
    client.git("add", "-A", cwd=folder)
    client.git("commit", "-qm", "Plan on the part", cwd=folder)
    data, _, _ = _board(client, tmp_path)
    assert _row(data, "LOST")["title"] == "Couriers book slots"
