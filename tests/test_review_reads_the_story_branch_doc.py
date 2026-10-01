"""A task's review reads the story doc from where forge task start does: the story branch's copy
while that branch exists, else the default branch's.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

import re
from pathlib import Path

from test_close import env  # noqa: F401  (env is a fixture)
from test_shortplan_briefs import NEW

STORY = "a-task-s-review-reads-the-story-doc-from"

OLD_ROW = "| T1 | Save a basket | Shoppers can save their basket |"
NEW_ROW = "| T1 | Save a basket | Shoppers can save their basket, but not share it |"


def test_1_review_carries_the_row_edited_on_the_story_branch(env):
    item, _ = env.start_approved_task(NEW, "T1", {"app.py": "print('saved')\n"})
    story_tree = Path(re.search(r"^worktree (.+)\n[^\n]*\nbranch refs/heads/story/SHOP$",
                                env.repo.git("worktree", "list", "--porcelain"), re.M)[1])
    doc = (story_tree / "plans" / "SHOP.md").read_text("utf-8")
    assert OLD_ROW in doc
    # The Tasks table sits under "For the builders", so this edit keeps the approval.
    env.commit(story_tree, "plans/SHOP.md", doc.replace(OLD_ROW, NEW_ROW), "Move sharing out of T1")

    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Shoppers can save their basket, but not share it" in env.prompt()
