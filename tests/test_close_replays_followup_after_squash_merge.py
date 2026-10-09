"""Real close and Git histories protect follow-up replay; only remote services are faked."""

import shlex
import subprocess
from pathlib import Path

import pytest

from test_close import body, env  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured, land_on_default, started

STORY = "stacked-replay"


def stacked(env, previous=False):
    repo = configured(env, previous)
    parent, parent_folder = started(repo, "Repair the underlying problem")
    parent_head = env.commit(parent_folder, "src/shared.py", "PARENT = True\n" + "# stable\n" * 20)
    env.commit(parent_folder, "src/parent_only.py", "PARENT_ONLY = True\n")
    fix, where = started(repo, "Repair the follow-up", cwd=parent_folder)
    own = "FOLLOWUP = True\n" + "# stable\n" * 20
    env.commit(where, "src/shared.py", own, "Repair the follow-up")
    return repo, parent, parent_head, fix, where, own


def remote_head(repo, fix):
    return repo.git("ls-remote", "--heads", "origin", f"refs/heads/fix/{fix}").split()[0]


def assert_not_ancestor(repo, commit, where):
    result = subprocess.run(["git", "merge-base", "--is-ancestor", commit, "HEAD"], cwd=where,
                            capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 1, result.stdout + result.stderr


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_replays_only_followup_commits_after_parent_squash_merges(env, previous):
    repo, parent, parent_head, fix, where, own = stacked(env, previous)
    # A follow-up may already have merged an earlier default-branch update.
    land_on_default(repo)
    repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    original_head = remote_head(repo, fix)
    land_on_default(repo, parent)
    land_on_default(repo, path="src/new_default.py")
    # An earlier merged default update is not an own change when default updates it again.
    writer = repo.path.parent / "default-writer"
    env.commit(writer, "src/unrelated.py", "OTHER = 2\n")
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    default_head = repo.git("rev-parse", "origin/main")

    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (where / "src/shared.py").read_text("utf-8") == own
    assert (where / "src/parent_only.py").read_text("utf-8") == "PARENT_ONLY = True\n"
    assert (where / "src/new_default.py").read_text("utf-8") == "OTHER = True\n"
    assert (where / "src/unrelated.py").read_text("utf-8") == "OTHER = 2\n"
    repo.git("merge-base", "--is-ancestor", default_head, "HEAD", cwd=where)
    assert_not_ancestor(repo, parent_head, where)
    assert_not_ancestor(repo, original_head, where)
    assert repo.git("diff", "--name-only", "origin/main", "HEAD", "--", "src", cwd=where) == "src/shared.py"
    assert remote_head(repo, fix) == repo.git("rev-parse", "HEAD", cwd=where)
    assert repo.git("status", "--porcelain", cwd=where) == ""


def test_2_close_aborts_replay_when_followups_own_commit_conflicts(env):
    repo, parent, _, fix, where, own = stacked(env)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    original_head = repo.git("rev-parse", "HEAD", cwd=where)
    land_on_default(repo, parent)
    writer = repo.path.parent / "default-writer"
    env.commit(writer, "src/shared.py", "DEFAULT = True\n" + "# stable\n" * 20)
    repo.git("push", "-q", "origin", "main", cwd=writer)

    closed = env.close(fix)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Replaying this fix's own commits onto main conflicts in src/shared.py." in closed.stderr
    assert "Next:" in closed.stderr and "rebase --rebase-merges=rebase-cousins --onto origin/main" in closed.stderr
    assert "rebase --continue" in closed.stderr and f"forge close {fix}" in closed.stderr
    assert f"git push --force-with-lease=refs/heads/fix/{fix}:{original_head} origin fix/{fix}" in closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == original_head
    assert remote_head(repo, fix) == original_head
    assert (where / "src/shared.py").read_text("utf-8") == own
    assert repo.git("status", "--porcelain", cwd=where) == ""
    assert env.review_calls() == []


def test_3_close_preserves_unknown_remote_commits_before_replaying(env):
    repo, parent, _, fix, where, own = stacked(env)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    original_head = repo.git("rev-parse", "HEAD", cwd=where)
    outsider = env.tmp / "other-writer"
    repo.git("clone", "-q", "--branch", f"fix/{fix}", repo.git("remote", "get-url", "origin"), str(outsider))
    other_head = env.commit(outsider, "src/other.py", "OTHER_WORK = True\n")
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=outsider)
    land_on_default(repo, parent)

    closed = env.close(fix)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "The remote branch has commits this checkout does not have, so Forge left it alone." in closed.stderr
    assert f"Next: fetch and reconcile fix/{fix}, then forge close {fix}" in closed.stderr
    assert remote_head(repo, fix) == other_head
    assert repo.git("rev-parse", "HEAD", cwd=where) == original_head
    assert (where / "src/shared.py").read_text("utf-8") == own
    assert env.review_calls() == []


def test_4_leased_replay_push_preserves_work_arriving_after_lease_is_captured(env):
    repo, parent, _, fix, where, _ = stacked(env)
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stderr
    if repo.git("status", "--porcelain", cwd=where):
        repo.git("add", "-A", cwd=where)
        repo.git("commit", "-qm", "Refresh the client's generated files", cwd=where)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    original_head = remote_head(repo, fix)
    remote = Path(repo.git("remote", "get-url", "origin"))
    outsider = env.tmp / "other-writer"
    repo.git("clone", "-q", "--branch", f"fix/{fix}", str(remote), str(outsider))
    other_head = env.commit(outsider, "src/other.py", "OTHER_WORK = True\n")
    repo.git("fetch", "-q", str(outsider), f"fix/{fix}", cwd=remote)
    land_on_default(repo, parent)
    # Advance the real remote after close captures its lease, before push advertises the new tip.
    hook = Path(repo.git("rev-parse", "--path-format=absolute", "--git-path", "hooks", cwd=where)) / "pre-rebase"
    action = f"git --git-dir={shlex.quote(remote.as_posix())} update-ref refs/heads/fix/{fix} {other_head} {original_head}\n"
    hook.write_text("#!/bin/sh\n" + action, encoding="utf-8")
    hook.chmod(0o755)

    closed = env.close(fix)
    assert closed.returncode != 0, closed.stdout + closed.stderr
    assert remote_head(repo, fix) == other_head, closed.stdout + closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == original_head
    assert closed.stderr.splitlines()[-2:] == [
        "Git refused the replayed push, so Forge restored the original commits in this checkout.",
        f"Next: check the remote branch and reconcile fix/{fix}, then forge close {fix}"]


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_5_fix_started_on_default_keeps_merging_default(env, previous):
    repo = configured(env, previous)
    fix, where = started(repo, "Repair an ordinary problem")
    original_head = env.commit(where, "src/own.py", "OWN = True\n")
    land_on_default(repo)
    default_head = repo.git("rev-parse", "origin/main")

    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    repo.git("merge-base", "--is-ancestor", original_head, "HEAD", cwd=where)
    repo.git("merge-base", "--is-ancestor", default_head, "HEAD", cwd=where)
    assert (where / "src/own.py").read_text("utf-8") == "OWN = True\n"
    assert (where / "src/unrelated.py").read_text("utf-8") == "OTHER = True\n"
    assert remote_head(repo, fix) == repo.git("rev-parse", "HEAD", cwd=where)


def test_6_replay_preserves_own_changes_committed_in_a_default_merge(env):
    repo, parent, parent_head, fix, where, own = stacked(env)
    proof = "The follow-up's changes were checked by its worker."
    # Merge bookkeeping is not worker evidence; keep the proof on the actual worker commit.
    repo.git("commit", "--amend", "-qm", "Repair the follow-up\n\nProof list:\n" + proof, cwd=where)
    land_on_default(repo)
    repo.git("merge", "-q", "--no-commit", "origin/main", cwd=where)
    merge_head = env.commit(where, "src/resolution.py", "OWN_MERGE_WORK = True\n",
                            "Keep the follow-up's merge amendment")
    land_on_default(repo, parent)

    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert (where / "src/resolution.py").read_text("utf-8") == "OWN_MERGE_WORK = True\n"
    assert (where / "src/shared.py").read_text("utf-8") == own
    assert_not_ancestor(repo, merge_head, where)
    assert_not_ancestor(repo, parent_head, where)
    assert repo.git("diff", "--name-only", "origin/main", "HEAD", "--", "src", cwd=where).splitlines() == [
        "src/resolution.py", "src/shared.py"]
    assert remote_head(repo, fix) == repo.git("rev-parse", "HEAD", cwd=where)
    assert proof in body(env.gh_calls("pr", "create")[-1])
