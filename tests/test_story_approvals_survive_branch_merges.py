"""A story approval survives a concurrent cold read on another machine.

Test audit: task start must honor the human's committed approval after a branch
merge. Keeping the local record on equal worker rounds discards that approval.
The fix-record regression cannot expose this because stories have no worker round.
Real read, approval, Git merge and task start own this proof, with no production seam.
"""
import json

import pytest

from test_story import DOC, claude_plan, ready, setup

STORY = "record-merge-conflicts"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("approver", ["local", "remote"])
def test_4_task_start_keeps_story_approval_after_a_concurrent_read(repo, claude_payload, monkeypatch, approver):
    setup(repo)
    local = ready(repo, "SHOP")
    synced = repo.forge("sync", cwd=local)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=local)
    repo.git("commit", "--allow-empty", "-q", "-m", "Install shared merge rules", cwd=local)
    repo.git("push", "-q", "origin", "story/SHOP", cwd=local)
    remote = repo.path.parent / "other approval machine"
    repo.git("clone", "-q", "--branch", "story/SHOP", repo.git("remote", "get-url", "origin"), str(remote))

    def command(where, *args, **kwargs):
        # Each machine has its own registered repos, as in a real two-machine run.
        with monkeypatch.context() as machine:
            for variable in ("APPDATA", "XDG_CONFIG_HOME"):
                machine.setenv(variable, str(repo.path.parent / f"config-{where.name}"))
            return repo.forge(*args, cwd=where, **kwargs)

    approved, reading = (local, remote) if approver == "local" else (remote, local)
    payload = claude_plan(claude_payload, DOC, cwd=approved)
    approval = command(approved, "hook", "approval", input=json.dumps(payload))
    assert approval.returncode == 0, approval.stdout + approval.stderr
    assert "Recorded the approval" in approval.stdout
    read = command(reading, "read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    repo.git("fetch", "-q", str(remote), "story/SHOP", cwd=local)

    repo.git("merge", "-q", "--no-edit", "FETCH_HEAD", cwd=local)
    repo.git("push", "-q", "origin", "story/SHOP", cwd=local)
    started = command(local, "task", "start", "SHOP/SAVE")

    assert started.returncode == 0, started.stdout + started.stderr
    assert "SHOP/SAVE" in started.stdout
