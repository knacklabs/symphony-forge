"""forge next never lists a part as waiting for itself; a part waits only for other items."""
import json

import pytest

from test_board import DOC
from test_board_dependency_timelines import _configured
from test_story import claude_plan, hook, ready, worktree

STORY = "next-no-self-wait"


def _waits(repo):
    """Each part's waits_for in forge next --json's dependency map."""
    board = json.loads(repo.forge("next", "--json").stdout)
    return {part["id"]: part["waits_for"] for story in board["dependency_maps"] for part in story["parts"]}


def _planned(repo, gh, tmp_path, claude_payload, history):
    _configured(repo, gh, tmp_path, history, ("SHOP",))
    story_tree = ready(repo, "SHOP", DOC)
    assert hook(repo, claude_plan(claude_payload, DOC, cwd=story_tree)).returncode == 0


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_1_a_part_started_here_and_not_pushed_waits_for_nothing(
        repo, gh, tmp_path, claude_payload, history):
    _planned(repo, gh, tmp_path, claude_payload, history)
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    # Its worktree goes and its branch was never pushed: only the local branch says it started.
    repo.git("worktree", "remove", "--force", str(worktree(repo, "task/SHOP-SAVE")))
    repo.git("push", "-q", "origin", "--delete", "task/SHOP-SAVE")

    shown = repo.forge("next").stdout
    board = repo.forge("next", "--json").stdout
    assert "SHOP/SAVE waits for SHOP/SAVE" not in shown + board, shown + board
    assert "SHOP/SAVE was started by" in shown, shown
    # A dependent part needs published, reviewed changes. Its advice must not
    # tell this machine to start the already claimed base again.
    assert "SHOP/SHOW waits for SHOP/SAVE to publish reviewed changes." in shown
    assert "SHOP/SHARE waits for SHOP/SAVE to publish reviewed changes." in shown
    assert "Next: forge task start SHOP/SAVE" not in shown + board, shown + board
    assert "SHOP/SAVE" not in _waits(repo)["SHOP/SAVE"]


@pytest.mark.parametrize("history", ["new", "adopted-v1.2.2"])
def test_2_a_part_whose_after_names_itself_is_a_cycle(repo, gh, tmp_path, claude_payload, history):
    _planned(repo, gh, tmp_path, claude_payload, history)
    doc = DOC.replace("`tests/test_basket.py` | none |", "`tests/test_basket.py` | SHOP/SAVE |")
    (worktree(repo, "story/SHOP") / "plans" / "SHOP.md").write_text(doc, encoding="utf-8")
    problem = "is malformed: Tasks row SAVE: its After list makes a cycle (SAVE -> SAVE)."

    read = repo.forge("read", "SHOP")
    assert read.returncode == 1
    assert problem in read.stderr, read.stderr
    shown = repo.forge("next").stdout
    assert problem in shown, shown
    assert "SHOP/SAVE waits for SHOP/SAVE" not in shown, shown
    assert "SHOP/SAVE" not in _waits(repo)["SHOP/SAVE"]
