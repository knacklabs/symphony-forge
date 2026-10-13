"""forge next never lists a part as waiting for itself; a part waits only for other items."""
import pytest

from test_board import DOC
from test_board_dependency_timelines import _configured
from test_story import claude_plan, hook, ready, worktree

STORY = "next-no-self-wait"


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_a_part_started_here_and_not_pushed_waits_for_nothing(
        repo, gh, tmp_path, claude_payload, history):
    _configured(repo, gh, tmp_path, history, ("SHOP",))
    story_tree = ready(repo, "SHOP", DOC)
    assert hook(repo, claude_plan(claude_payload, DOC, cwd=story_tree)).returncode == 0
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    # Its worktree goes and its branch was never pushed: only the local branch says it started.
    repo.git("worktree", "remove", "--force", str(worktree(repo, "task/SHOP-SAVE")))
    repo.git("push", "-q", "origin", "--delete", "task/SHOP-SAVE")

    shown = repo.forge("next").stdout
    board = repo.forge("next", "--json").stdout
    assert "SHOP/SAVE waits for SHOP/SAVE" not in shown + board, shown + board
    assert "SHOP/SAVE was started by" in shown, shown
    assert "Next: forge task start SHOP/SAVE" not in shown + board, shown + board
