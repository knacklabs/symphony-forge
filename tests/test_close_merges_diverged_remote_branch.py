"""Close preserves both histories after a pushed commit changes locally.

Real git supplies the rejection, merge and conflict. Only GitHub and review are faked.
"""

import pytest

from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FIX-DIVERGED-BRANCH-MERGE"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
@pytest.mark.parametrize("different", [False, True], ids=["same-tree", "different-trees"])
def test_1_close_merges_diverged_branch_and_pushes_without_losing_history(env, previous, different):
    client(env, previous)
    item, where = env.start_fix()
    repo = env.repo
    repo.git("push", "-q", "origin", "fix/tidy-readme", cwd=where)
    remote = repo.git("rev-parse", "HEAD", cwd=where)
    if different:
        (where / "extra.txt").write_text("Keep the local addition\n", encoding="utf-8")
        repo.git("add", "extra.txt", cwd=where)
    repo.git("commit", "--amend", "-qm", "Amend the work", cwd=where)
    local = repo.git("rev-parse", "HEAD", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "The local and remote branches diverged" in closed.stdout
    assert "amended or rebased commit" in closed.stdout
    assert ("Their trees differ." if different else "Their trees are the same.") in closed.stdout
    assert "Ready: tidy-readme" in closed.stdout
    pushed = repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
    assert pushed == repo.git("rev-parse", "HEAD", cwd=where)
    for commit in (remote, local):
        repo.git("merge-base", "--is-ancestor", commit, pushed, cwd=where)
    assert (where / "app.py").read_text("utf-8") == "print('hello')\n"
    if different:
        assert (where / "extra.txt").read_text("utf-8") == "Keep the local addition\n"
    assert repo.git("status", "--porcelain", cwd=where) == ""


def test_2_close_leaves_conflicting_merge_for_resolution_and_can_resume(env):
    item, where = env.start_fix()
    repo = env.repo
    repo.git("push", "-q", "origin", "fix/tidy-readme", cwd=where)
    remote = repo.git("rev-parse", "HEAD", cwd=where)
    (where / "app.py").write_text("print('amended')\n", encoding="utf-8")
    repo.git("add", "app.py", cwd=where)
    repo.git("commit", "--amend", "-qm", "Amend the greeting", cwd=where)
    local = repo.git("rev-parse", "HEAD", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 1
    assert "The local and remote branches diverged" in closed.stdout
    assert "Their trees differ." in closed.stdout
    assert "The merge of the remote branch conflicts in app.py." in closed.stderr
    assert "resolve the conflicts and commit the merge" in closed.stderr
    assert f"then forge close {item}" in closed.stderr
    assert "forge doctor" not in closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == local
    assert repo.git("rev-parse", "MERGE_HEAD", cwd=where) == remote
    assert repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0] == remote
    assert not env.review_calls()
    env.commit(where, "app.py", "print('resolved')\n", "Resolve the merge")
    resumed = env.close(item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    pushed = repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0]
    for commit in (remote, local):
        repo.git("merge-base", "--is-ancestor", commit, pushed, cwd=where)


@pytest.mark.platform
def test_3_close_names_merge_failure_and_preserves_history_when_a_hook_refuses(env):
    item, where = env.start_fix()
    repo = env.repo
    repo.git("push", "-q", "origin", "fix/tidy-readme", cwd=where)
    remote = repo.git("rev-parse", "HEAD", cwd=where)
    repo.git("commit", "--amend", "-qm", "Amend the work", cwd=where)
    local = repo.git("rev-parse", "HEAD", cwd=where)
    hooks = env.tmp / "merge-hooks"
    hooks.mkdir()
    hook = hooks / "pre-merge-commit"
    hook.write_text("#!/bin/sh\necho 'merge hook refused' >&2\nexit 1\n", encoding="utf-8")
    hook.chmod(0o755)
    repo.git("config", "core.hooksPath", hooks.as_posix(), cwd=where)

    closed = env.close(item)

    assert closed.returncode == 1
    assert "The merge of the remote branch failed: merge hook refused" in closed.stderr
    assert f"Next: in {where}, finish or abort the merge, then retry this command" in closed.stderr
    assert "forge doctor" not in closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == local
    assert repo.git("rev-parse", "MERGE_HEAD", cwd=where) == remote
    assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == ""
    assert repo.git("ls-remote", "origin", "fix/tidy-readme").split()[0] == remote
    assert not env.review_calls()
