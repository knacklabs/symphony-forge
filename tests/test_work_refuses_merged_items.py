"""Work must refuse a merged pull request before it admits another worker round.

Only GitHub is faked at its edge. Real item creation, git and the work command
prove the refusal leaves the branch and checkout alone, even after cleanup.
"""
import json

import pytest

from test_task import story
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "FIX-WORK-MERGED-ITEM"


@pytest.mark.parametrize("client, kind, removed", [
    (False, "fix", False), (False, "fix", True),
    (False, "task", False), (False, "task", True),
    (True, "fix", True),
], indirect=["client"], ids=["new-fix", "new-cleaned-fix", "new-task", "new-cleaned-task",
                            "adopted-cleaned-fix"])
def test_1_work_refuses_merged_items_and_points_to_a_follow_up(client, gh, kind, removed):
    log = install_claude(client)
    if kind == "task":
        story(client)
        item, branch = "BOARD/PAGE", "task/BOARD-PAGE"
        made = client.forge("task", "start", item)
        folder = client.path.parent / f"{client.path.name}-BOARD-PAGE"
    else:
        item, branch = "correct-spelling", "fix/correct-spelling"
        made = client.forge("fix", "start", "Correct spelling", "--done", "Correct spelling",
                            "--kind", "mechanical")
        folder = client.path.parent / f"{client.path.name}-fix-{item}"
    assert made.returncode == 0, made.stdout + made.stderr
    # GitHub can merge the PR before this clone fetches the default branch.
    # A local 'started' record must not allow work on that branch again.
    gh.respond("pr", "list", "--head", branch, "--state", "all",
               stdout=json.dumps([{"number": 1025, "state": "MERGED"}]))
    head = client.git("rev-parse", branch)
    if removed:
        client.git("worktree", "remove", str(folder))
    trees = client.git("worktree", "list", "--porcelain")
    refused = client.forge("work", item)
    assert refused.returncode == 1
    assert refused.stderr == (
        f"The pull request for {item} is already merged. Start a new fix for follow-up work.\n"
        'Next: forge fix start "<why>" --done "<done when>"\n')
    assert client.git("rev-parse", branch) == head
    assert client.git("worktree", "list", "--porcelain") == trees
    assert folder.exists() == (not removed)
    if not removed:
        assert client.git("status", "--porcelain", cwd=folder) == ""
    assert calls(log) == []
