"""Work must refuse a merged pull request before it admits another worker round.

Real item creation, a squash merge in the remote, and the work command prove
the refusal leaves the branch and checkout alone, even after cleanup.
"""
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
    # A squash merge publishes the item's record without changing its local
    # 'started' record or this clone's stale origin/main. Work must fetch it.
    head = client.git("rev-parse", branch)
    remote = client.git("remote", "get-url", "origin")
    client.git("push", "-q", "origin", branch)
    landed = client.git("commit-tree", client.git("rev-parse", f"{branch}^{{tree}}"),
                        "-p", client.git("rev-parse", "main"), "-m", "Squash the pull request")
    client.git("push", "-q", "origin", f"{landed}:refs/heads/merged-item")
    client.git("update-ref", "refs/heads/main", landed, cwd=remote)
    if removed:
        client.git("worktree", "remove", str(folder))
    trees = client.git("worktree", "list", "--porcelain")
    github_calls = gh.calls()
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
    assert gh.calls() == github_calls, "Work must not require GitHub's API to check merged work"
