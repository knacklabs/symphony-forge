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
    """TURN-1 approved with a task T4, and SHOP approved with its first task SAVE waiting for
    `after`, both planned before T4 merges."""
    setup(repo, keys=("SHOP", "TURN-1"))
    for key, doc in (("TURN-1", OTHER), ("SHOP", DOC.replace(
            "`tests/test_basket.py` | none |", f"`tests/test_basket.py` | {after} |"))):
        path = ready(repo, key, doc)
        assert hook(repo, claude_plan(claude_payload, doc, cwd=path)).returncode == 0


def test_1_a_task_waits_for_another_story_s_task_then_starts_once_it_merges(repo, claude_payload):
    _plans(repo, claude_payload, "TURN-1/T4")
    waiting = "SHOP/SAVE waits for TURN-1/T4 to merge first."

    def waits():
        shown = repo.forge("next").stdout
        assert waiting in shown, shown
        assert "Next: forge task start SHOP/SAVE" not in shown, shown
        refused = repo.forge("task", "start", "SHOP/SAVE")
        assert refused.returncode == 1
        assert refused.stderr == f"{waiting}\nNext: forge next\n"

    waits()
    started = repo.forge("task", "start", "TURN-1/T4")
    assert started.returncode == 0, started.stderr
    waits()  # started but not merged still holds it back

    # T4's worker commits its code, and its pull request merges into the default branch.
    turn = worktree(repo, "task/TURN-1-T4")
    (turn / "src").mkdir()
    (turn / "src" / "turn.py").write_text("TURNS = 1\n", encoding="utf-8")
    repo.git("add", "-A", cwd=turn)
    repo.git("commit", "-q", "-m", "Save turns", cwd=turn)
    repo.git("merge", "-q", "--no-ff", "-m", "Save turns (#1)", "task/TURN-1-T4")
    repo.git("push", "-q", "origin", "main")

    shown = repo.forge("next").stdout
    assert "waits for TURN-1/T4" not in shown, shown
    assert "Next: forge task start SHOP/SAVE" in shown, shown
    started = repo.forge("task", "start", "SHOP/SAVE")
    assert started.returncode == 0, started.stderr
    shop = worktree(repo, "task/SHOP-SAVE")
    assert (shop / "src" / "turn.py").read_text(encoding="utf-8") == "TURNS = 1\n"
    assert "TURN-1/T4" in (shop / "plans" / "SHOP.md").read_text(encoding="utf-8")
    assert repo.git("status", "--porcelain", cwd=shop) == ""


def test_2_an_after_naming_a_task_the_other_story_lacks_is_malformed(repo, claude_payload):
    _plans(repo, claude_payload, "TURN-1/T4")
    shop = worktree(repo, "story/SHOP")
    doc = DOC.replace("`tests/test_basket.py` | none |", "`tests/test_basket.py` | TURN-1/T9 |")
    (shop / "plans" / "SHOP.md").write_text(doc, encoding="utf-8")
    problem = "Tasks row SAVE: After TURN-1/T9 is not a task in the plan of TURN-1"

    read = repo.forge("read", "SHOP")
    assert read.returncode == 1
    assert read.stderr == (f"plans/SHOP.md is malformed: {problem}.\n"
                           "Next: edit plans/SHOP.md, then run forge next\n")
    shown = repo.forge("next").stdout
    assert f"is malformed: {problem}." in shown, shown

    # forge-pr-check reads the doc at the pull request's head and refuses it the same way.
    base = repo.git("rev-parse", "main")
    repo.git("checkout", "-q", "-b", "task/SHOP-SAVE", "story/SHOP")
    repo.write(".factory/stories/SHOP/tasks/SAVE.json",
               '{"branch": "task/SHOP-SAVE", "status": "working", "steps": []}\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Start task SAVE")
    pr_check = ("hook", "pr-check", "--base", base, "--head", "HEAD", "--branch", "task/SHOP-SAVE")
    known = repo.forge(*pr_check)
    assert "malformed" not in known.stdout + known.stderr, known.stdout + known.stderr
    repo.write("plans/SHOP.md", doc)
    repo.git("commit", "-q", "-am", "Wait for a task TURN-1 doesn't have")
    checked = repo.forge(*pr_check)
    assert checked.returncode != 0
    assert f"The story doc plans/SHOP.md is malformed: {problem}." in checked.stdout + checked.stderr
