"""Close publishes a clean final change despite an intermediate replay conflict."""

from pathlib import Path

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_replays_followup_after_squash_merge import stacked
from test_stack_start import configured, start
from test_stacked_fixes_count_only_their_own_changes import land_on_default

STORY = "squash-replay-on-conflict"


@pytest.mark.parametrize("kind", ["part", "fix"])
def test_1_close_squashes_only_intermediate_conflicts(env, kind):
    # Audit: close must retain merged content, history and evidence, and land must
    # recognise a built fix. Earlier cases omit separate planning and old reviews.
    # Real Git and commands own the result; only remote services are faked.
    if kind == "part":
        repo = configured(env, False)
        parent, _ = start(repo, "A")
        env.commit(parent, "app.py", "A_VALUE = 1\n", "Build the base part")
        closed = env.close("STACK/A")
        assert closed.returncode == 0, closed.stdout + closed.stderr
        part, _ = start(repo, "B")
        item, branch, path, own_path = "STACK/B", "task/STACK-B", "app.py", "use.py"
    else:
        repo, parent, _, item, part, _ = stacked(env)
        branch, path, own_path = f"fix/{item}", "src/shared.py", "src/repair.py"
    solo = env.tmp / "pickup"
    repo.git("clone", "-q", "--no-local", repo.git("remote", "get-url", "origin"), str(solo))
    plan = ("Before coding:\nNeed: Keep the separate planning evidence.\n"
            "Simplest option: Reuse the final merged tree.\nExisting code reused: Git.\n\n"
            "Ruling: Keep this separate plan - it records the worker choice.\n"
            "Declined: Unneeded cache (use.py): not worth the code - a value is enough.\n"
            "Spotted: improve use.py:1 Explain the value later.")
    repo.git("commit", "--allow-empty", "-qm", plan, cwd=part)
    env.commit(part, "witness.py", "WITNESS = 1\n", "Keep a stable review witness")
    env.commit(part, path, "VALUE = 2\n", "Try an intermediate value")
    note = "The witness value is missing"
    env.reviews(blocked(finding("P1", note, "witness.py")))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    reason = "witness.py:1 the constant provides the value"
    dismissed = env.close(item, "--dismiss", "1", "--because", reason)
    assert dismissed.returncode == 0, dismissed.stdout + dismissed.stderr
    env.commit(part, own_path, "OWN_VALUE = 2\n", "Keep the part's work")
    env.reviews(CLEAN)
    second = env.close(item)
    assert second.returncode == 0, second.stdout + second.stderr
    proof = "Functional check: read the final value.\n\nProof list: tests/test_work.py::test_value"
    env.commit(part, path, "VALUE = 3\n", "Keep the final value\n\n" + proof)
    if kind == "fix":
        land_on_default(repo, parent)
    writer = repo.path.parent / "default-writer"
    if kind == "part":
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
        repo.git("fetch", "-q", "origin", "task/STACK-A", cwd=writer)
        repo.git("merge", "-q", "--squash", "FETCH_HEAD", cwd=writer)
        repo.git("commit", "-qm", "Merge STACK/A", cwd=writer)
    else:
        # The ordinary merge conflicts on inherited parent content. The part's own
        # final changes still merge cleanly once that inherited content is excluded.
        env.commit(writer, "src/parent_only.py", "PARENT_ONLY = False\n")
    env.commit(writer, path, "VALUE = 3\n", "Change the same value on main")
    env.commit(writer, "default_note.py", "NOTE = 2\n", "Keep a main-only file")
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    default = repo.git("rev-parse", "origin/main")

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    repo.git("merge-base", "--is-ancestor", default, "HEAD", cwd=part)
    assert (part / path).read_text("utf-8") == "VALUE = 3\n"
    assert (part / own_path).read_text("utf-8") == "OWN_VALUE = 2\n"
    assert (part / "default_note.py").read_text("utf-8") == "NOTE = 2\n"
    assert (part / "witness.py").read_text("utf-8") == "WITNESS = 1\n"
    if kind == "fix":
        assert (part / "src/parent_only.py").read_text("utf-8") == "PARENT_ONLY = False\n"
    assert repo.git("rev-list", "--count", f"{default}..HEAD", "--", path, own_path,
                    cwd=part) == "1"
    messages = repo.git("log", "--format=%B", f"{default}..HEAD", cwd=part)
    assert plan in messages
    assert proof in messages
    assert repo.git("ls-remote", "--heads", "origin", branch).split()[0] == repo.git(
        "rev-parse", "HEAD", cwd=part)
    assert repo.git("status", "--porcelain", cwd=part) == ""

    # A teammate must receive the old reviews too. A network clone gets only what the
    # remote refs reach; a plain clone from a folder would copy the squashed commits.
    clone = env.tmp / "teammate"
    repo.git("clone", "-q", "--no-local", "--branch", branch,
             repo.git("remote", "get-url", "origin"), str(clone))
    if kind == "fix":
        landed = repo.forge("land", item, cwd=clone)
        assert f"Building {item}." not in landed.stdout, landed.stdout + landed.stderr
        assert f"Closing {item}." in landed.stdout, landed.stdout + landed.stderr
    env.commit(clone, own_path, "OWN_VALUE = 3\n", "Check on another machine")
    # The reviewer repeats the dismissed finding. Its cited line is unchanged, so the
    # dismissal must still hold although the clone has none of the squashed commits.
    env.reviews(blocked(finding("P1", note, "witness.py")))
    checked = repo.forge("close", item, cwd=clone)
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert note in env.prompt()
    assert reason in env.prompt()
    assert "Keep the separate planning evidence" in env.prompt()

    # This teammate cloned before the branch had its reviews, so only a fetch of the
    # branch and of its replay tag can bring the commits that the reviews cite.
    picked = repo.forge("close", item, cwd=solo)
    assert picked.returncode == 0, picked.stdout + picked.stderr
    listing = repo.git("worktree", "list", "--porcelain", cwd=solo).split("\n\n")
    tree = Path(next(block.splitlines()[0].removeprefix("worktree ") for block in listing
                     if f"branch refs/heads/{branch}" in block.splitlines()))
    env.commit(tree, own_path, "OWN_VALUE = 4\n", "Check after a pick-up")
    again = repo.forge("close", item, cwd=solo)
    assert again.returncode == 0, again.stdout + again.stderr
