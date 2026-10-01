"""A plan's After may name another story's task as KEY/TASK: the task waits for that task's pull
request to merge, and a plan naming a task the other story doesn't have is malformed."""
from __future__ import annotations

import json

from test_story import DOC, claude_plan, hook, ready, setup, worktree

STORY = "a-plan-s-after-column-can-only-name-task"

OTHER = (DOC.replace("Shoppers can save a basket", "Turns take one click")
         .replace("| SAVE | Save baskets |", "| T4 | Save turns |")
         .replace("`tests/test_page.py` | SAVE |", "`tests/test_page.py` | T4 |")
         .replace("`src/basket.py`", "`src/turn.py`").replace("`src/page.py`", "`src/turn_page.py`"))


def _plans(repo, claude_payload, after):
    """TURN-1 planned with a task T4, and SHOP approved with SHOW waiting for `after`."""
    setup(repo, keys=("SHOP", "TURN-1"))
    ready(repo, "TURN-1", OTHER)
    doc = DOC.replace("`tests/test_page.py` | SAVE |", f"`tests/test_page.py` | SAVE, {after} |")
    shop = ready(repo, "SHOP", doc)
    assert hook(repo, claude_plan(claude_payload, doc, cwd=shop)).returncode == 0


def _merge_save(repo):
    """SHOP/SAVE merged, so only the other story's task still holds SHOW back."""
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    repo.git("merge", "-q", "--no-ff", "-m", "Save baskets", "task/SHOP-SAVE")
    repo.git("push", "-q", "origin", "main")


def test_1_a_task_waits_for_another_story_s_task_then_starts_once_it_merges(repo, claude_payload):
    _plans(repo, claude_payload, "TURN-1/T4")
    _merge_save(repo)

    shown = repo.forge("next").stdout
    assert "SHOP/SHOW waits for TURN-1/T4 to merge first." in shown, shown
    assert "Next: forge task start SHOP/SHOW" not in shown, shown
    refused = repo.forge("task", "start", "SHOP/SHOW")
    assert refused.returncode == 1
    assert refused.stderr == "SHOP/SHOW waits for TURN-1/T4 to merge first.\nNext: forge next\n"

    # TURN-1/T4's pull request merges: its state reaches the default branch.
    repo.write(".factory/stories/TURN-1/tasks/T4.json", json.dumps({"status": "merged"}))
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Save turns")
    repo.git("push", "-q", "origin", "main")

    shown = repo.forge("next").stdout
    assert "waits for TURN-1/T4" not in shown, shown
    assert "Next: forge task start SHOP/SHOW" in shown, shown
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stderr


def test_2_an_after_naming_a_task_the_other_story_lacks_is_malformed(repo, claude_payload):
    _plans(repo, claude_payload, "TURN-1/T4")
    shop = worktree(repo, "story/SHOP")
    doc = DOC.replace("`tests/test_page.py` | SAVE |", "`tests/test_page.py` | SAVE, TURN-1/T9 |")
    (shop / "plans" / "SHOP.md").write_text(doc, encoding="utf-8")
    problem = "Tasks row SHOW: After TURN-1/T9 is not a task in the plan of TURN-1"

    read = repo.forge("read", "SHOP")
    assert read.returncode == 1
    assert read.stderr == (f"plans/SHOP.md is malformed: {problem}.\n"
                           "Next: edit plans/SHOP.md, then run forge next\n")
    shown = repo.forge("next").stdout
    assert f"is malformed: {problem}." in shown, shown
