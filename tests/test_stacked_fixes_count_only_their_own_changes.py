"""A follow-up fix owns its size and interface checks across its parent's squash merge.

Real init/sync, fix start and git hooks are exercised; only GitHub is faked. The PR size
gate must reach the separate missing-review refusal when the fix is small enough.
"""
import subprocess
from pathlib import Path

import pytest

from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_githooks import commit, push

STORY = "stacked-fix-count"


def configured(env, previous):
    config = (env.repo.path / "forge.toml").read_text("utf-8") + 'repo = "client"\n'
    client(env, previous)
    repo = env.repo
    repo.write("forge.toml", config)
    repo.write("docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "Owner"\n---\n\n# Client sign-off\n')
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure the signed-off client")
    repo.git("push", "-q", "origin", "main")
    writer = repo.path.parent / "default-writer"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    return repo


def started(repo, why, cwd=None):
    done = repo.forge("fix", "start", why, "--done", "Only this fix's changes count", cwd=cwd)
    assert done.returncode == 0, done.stdout + done.stderr
    return done.stdout.split()[2], Path(done.stdout.splitlines()[0].split(" in ", 1)[1])


def pr_check(repo, fix, head):
    # The shipped CI checkout has no commit identity; only setup and hook commits need one.
    config = repo.path.parent / "runner-gitconfig"
    config.write_text("[user]\n\tuseConfigOnly = true\n", "utf-8")
    with pytest.MonkeyPatch.context() as identity:
        identity.setenv("GIT_CONFIG_GLOBAL", str(config))
        for ident in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"):
            missing = subprocess.run(["git", "var", ident], cwd=repo.path,
                                     capture_output=True, text=True, encoding="utf-8")
            assert missing.returncode != 0, missing.stdout
        return repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "main"),
                          "--head", head, "--branch", f"fix/{fix}")


def land_on_default(repo, parent=None, path="src/unrelated.py"):
    # A separate clone represents the human landing work, with its own local hooks.
    writer = repo.path.parent / "default-writer"
    if parent:
        repo.git("fetch", "-q", str(repo.path), f"fix/{parent}", cwd=writer)
        repo.git("merge", "-q", "--squash", "FETCH_HEAD", cwd=writer)
    else:
        target = writer / path
        target.parent.mkdir(exist_ok=True)
        target.write_text("OTHER = True\n", "utf-8")
        repo.git("add", "-A", cwd=writer)
    repo.git("commit", "-qm", "Land other work", cwd=writer)
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "-q", "--ff-only", "origin/main")


def check_limits(repo, fix, where):
    """Each gate accepts five own paths and refuses the sixth and an own interface."""
    allowed = commit(where, flags=("--allow-empty",))
    assert allowed.returncode == 0, allowed.stderr
    head = repo.git("rev-parse", "HEAD", cwd=where)
    pushed = push(where, f"fix/{fix}")
    assert pushed.returncode == 0, pushed.stderr
    checked = pr_check(repo, fix, head)
    assert checked.returncode == 1
    assert checked.stderr.splitlines()[-2:] == [
        f"The committed review at the head of fix/{fix} is missing.", f"Next: forge close {fix}"]

    for path, hook_problem, pr_problem in (
        ("src/sixth.py", "changes 6 code files, over the limit of 5",
         "changes 6 code files, over the limit of 5"),
        ("api/routes/followup.py", "changes the interface api/routes/followup.py",
         "changes the interface path api/routes/followup.py"),
    ):
        refused = commit(where, path)
        assert refused.returncode != 0
        assert f"Fix {fix} {hook_problem}, so it has to become a story" in refused.stderr
        # A commit made on a machine with no hooks still gets checked at push and in CI.
        # commit-tree makes that object without bypassing or changing the installed hooks.
        tree = repo.git("write-tree", cwd=where)
        candidate = repo.git("commit-tree", tree, "-p", head, "-m", "Unhooked machine", cwd=where)
        refused = push(where, f"{candidate}:refs/heads/fix/{fix}")
        assert refused.returncode != 0
        assert f"Fix {fix} {hook_problem}, so it has to become a story" in refused.stderr
        checked = pr_check(repo, fix, candidate)
        assert checked.returncode == 1
        assert checked.stderr.splitlines()[-2].startswith(
            f"The fix on fix/{fix} {pr_problem}, and has no allow-large reason.")
        repo.git("reset", "-q", "HEAD", "--", path, cwd=where)
        (where / path).unlink()


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_stacked_fix_counts_only_own_paths_before_and_after_parent_lands(env, previous):
    repo = configured(env, previous)
    parent, parent_folder = started(repo, "Repair the underlying item")
    allowed = repo.forge("fix", "allow-large", "The underlying item needs six files and a route",
                         cwd=parent_folder)
    assert allowed.returncode == 0, allowed.stderr
    synced = repo.forge("sync", cwd=parent_folder)
    assert synced.returncode == 0, synced.stderr
    inherited = [*(f"src/parent{n}.py" for n in range(6)), "api/routes/parent.py"]
    committed = commit(parent_folder, *inherited)
    assert committed.returncode == 0, committed.stderr
    fix, where = started(repo, "Repair its findings", cwd=parent_folder)
    for path in inherited:
        assert (where / path).read_text("utf-8") == f"{path}\n"

    # Editing one inherited path is still this fix's own work, alongside four new paths.
    own = ["src/parent0.py", *(f"src/own{n}.py" for n in range(4))]
    for path in own:
        target = where / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("FOLLOWUP = True\n", "utf-8")
    repo.git("add", "-A", cwd=where)
    committed = subprocess.run(["git", "commit", "-qm", "Repair the findings"], cwd=where,
                               capture_output=True, text=True, encoding="utf-8")
    assert committed.returncode == 0, committed.stderr
    check_limits(repo, fix, where)

    # Default-only changes merged before the parent lands must not count either.
    land_on_default(repo)
    repo.git("merge", "-q", "origin/main", cwd=where)
    check_limits(repo, fix, where)

    # Squash landing does not make the recorded start an ancestor of main. Merging main
    # must drop the inherited paths while retaining this fix's edit of a parent's file.
    land_on_default(repo, parent)
    check_limits(repo, fix, where)
    merged = subprocess.run(["git", "merge", "-q", "origin/main"], cwd=where,
                            capture_output=True, text=True, encoding="utf-8")
    assert merged.returncode == 1, merged.stdout + merged.stderr
    assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == "src/parent0.py"
    # The parent's squash commit has separate ancestry, so preserve the follow-up's edit
    # while resolving the expected add/add conflict. The real commit checks MERGE_HEAD.
    (where / "src/parent0.py").write_text("FOLLOWUP = True\n", "utf-8")
    repo.git("add", "src/parent0.py", cwd=where)
    repo.git("commit", "-qm", "Keep the follow-up while merging its landed parent", cwd=where)
    check_limits(repo, fix, where)


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_ordinary_fix_keeps_using_the_default_branch(env, previous):
    repo = configured(env, previous)
    fix, where = started(repo, "Repair an ordinary problem")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stderr
    committed = commit(where, *(f"src/own{n}.py" for n in range(5)))
    assert committed.returncode == 0, committed.stderr
    check_limits(repo, fix, where)
    # An unrelated main change does not become a sixth fix path after merging it.
    land_on_default(repo)
    repo.git("merge", "-q", "origin/main", cwd=where)
    check_limits(repo, fix, where)

    # Starting from a branch whose item already landed uses the current default again.
    land_on_default(repo, fix)
    land_on_default(repo, path="src/after_parent.py")
    _, following = started(repo, "Repair after its item landed", cwd=where)
    assert (following / "src/after_parent.py").read_text("utf-8") == "OTHER = True\n"
