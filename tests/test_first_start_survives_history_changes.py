"""Starting a fix-based story and rebuilding task history keep the original start time."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from test_board_after_upgrade import History, NOW
from test_close import env  # noqa: F401
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-EXACT-WAIT-TIMES"


@pytest.mark.parametrize(
    ("task", "from_fix"),
    [("T1", None), ("SPEC", "keep-baskets")],
    ids=["ordinary-task", "promoted-fix-task"],
)
def test_3_upgrade_uses_saved_task_start_when_early_commits_share_rewrite_time(
        unsynced_up, monkeypatch, task, from_fix):
    history = History(unsynced_up, monkeypatch)
    repo = history.repo
    branch = f"task/SHOP-{task}"
    path = f".factory/stories/SHOP/tasks/{task}.json"
    where = history.up.tmp / "rewritten-task"
    repo.git("worktree", "add", "-q", "-b", branch, where.as_posix(), "main")

    started_at = NOW - timedelta(days=5)
    rewritten_at = NOW - timedelta(days=1)
    state = {"kind": "task", "branch": branch, "status": "working",
             "why": "Readers see a saved basket", "done_when": "The basket stays saved",
             "base": repo.git("rev-parse", "main"),
             "steps": [{"step": "start", "at": started_at.isoformat()}]}
    if from_fix:
        state["from_fix"] = from_fix
    history.commit(where, path, json.dumps(state), "Start the task", rewritten_at)
    history.commit(where, "basket.py", "SAVED = True\n", "Keep the basket", rewritten_at)
    head = repo.git("rev-parse", "HEAD", cwd=where)
    repo.git("push", "-q", "origin", branch)
    repo.git("push", "-q", "origin", f"{head}:refs/pull/18/head")
    history.prs.append({"number": 18, "headRefName": branch, "headRefOid": head,
                        "baseRefName": "main", "state": "OPEN", "isDraft": False,
                        "title": "Keep the basket", "body": "Owner notes remain.\n",
                        "mergedAt": None, "mergedBy": None,
                        "author": {"login": "starter", "name": "Original Starter"},
                        "url": "https://github.com/acme/shop/pull/18"})
    history.publish()
    history.at(NOW)

    upgraded = history.up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    body = history.stored()[18]["body"]
    how_it_went = body.split("## How it went\n", 1)[1].split("<!-- forge:history", 1)[0]
    assert "unmeasured time: 5 days" in how_it_went
