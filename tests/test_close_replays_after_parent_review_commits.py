"""A story part started on its parent's unmerged branch closes after the parent is squash-merged.

Real task start, close and Git histories; only GitHub and the review engine are faked.
"""

import json

import pytest

from test_close import env  # noqa: F401
from test_stack_start import configured, start

pytestmark = pytest.mark.platform

STORY = "stacked-replay-parent-review"
RECORD = ".factory/stories/STACK/tasks/A.json"
OWN_WORK = """Build the stacked part

Before coding:
Need: the part reads the saved value.
Simplest option: one constant.
Existing code reused: none.

Proof list:
- Done when 1: tests/test_work.py::test_value, the part's own value is read.

Functional check: ran the part and read its own value."""


def parent_commits(env, folder, record=0, app=""):
    """What a parent's close leaves after a review: a change to its record and maybe to a file."""
    if record:
        state = json.loads((folder / RECORD).read_text("utf-8"))
        state["round"] = record
        env.commit(folder, RECORD, json.dumps(state, indent=2) + "\n", f"Review of STACK/A: round {record}")
    if app:
        env.commit(folder, "app.py", app, "Change the parent's file")
    env.repo.git("push", "-q", "origin", "task/STACK-A", cwd=folder)


# What the parent does after the part picked up its review commits and a draft edit of app.py.
AFTER = {"record": {"record": 3}, "draft taken out": {"app": "A_VALUE = 1\n"}, "nothing": {}}


def parent_merged_after_part_picked_up_its_review_commits(env, previous, after):
    repo = configured(env, previous)
    parent, _ = start(repo, "A")
    env.commit(parent, "app.py", "A_VALUE = 1\n", "Build the base part")
    closed = env.close("STACK/A")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    part, _ = start(repo, "B")
    env.commit(part, "use.py", "B_VALUE = 1\n", OWN_WORK)
    parent_commits(env, parent, 2, "A_VALUE = 1\nA_DRAFT = 1\n")
    repo.git("fetch", "-q", "origin")
    repo.git("merge", "-q", "--no-edit", "origin/task/STACK-A", cwd=part)
    parent_commits(env, parent, **AFTER[after])
    writer = repo.path.parent / "default-writer"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(writer))
    repo.git("fetch", "-q", "origin", "task/STACK-A", cwd=writer)
    repo.git("merge", "-q", "--squash", "FETCH_HEAD", cwd=writer)
    repo.git("commit", "-qm", "Merge STACK/A", cwd=writer)
    env.commit(writer, "default_note.py", "NOTE = 1\n", "Move the default branch")
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    return repo, part


@pytest.mark.parametrize("previous,after", [(False, "record"), (False, "draft taken out"), (True, "record")],
                         ids=["new-record", "new-draft-taken-out", "previously-adopted-record"])
def test_1_close_replays_only_the_parts_own_work_after_the_parent_merges(env, previous, after):
    repo, part = parent_merged_after_part_picked_up_its_review_commits(env, previous, after)
    before = len(env.review_calls())

    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "conflicts in" not in closed.stderr
    # The parent's record and file stay as the default branch has them; the draft does not return.
    for path in (RECORD, "app.py", "default_note.py"):
        assert (part / path).read_text("utf-8").rstrip("\n") == repo.git("show", f"origin/main:{path}")
    assert (part / "use.py").read_text("utf-8") == "B_VALUE = 1\n"
    own = repo.git("diff", "--name-only", "origin/main", "HEAD", cwd=part).splitlines()
    assert "use.py" in own and not {RECORD, "app.py"} & set(own)
    # The review ran after the replay and found the worker's evidence, which the replay kept.
    assert len(env.review_calls()) == before + 1
    assert "the part's own value is read" in env.prompt()
    messages = repo.git("log", "--format=%B", "origin/main..HEAD", cwd=part)
    for kept in ("Before coding:", "Proof list:", "Functional check: ran the part"):
        assert kept in messages
    assert repo.git("ls-remote", "--heads", "origin", "task/STACK-B").split()[0] == repo.git(
        "rev-parse", "HEAD", cwd=part)


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_close_keeps_uncommitted_edits_when_the_replay_cannot_start(env, previous):
    repo, part = parent_merged_after_part_picked_up_its_review_commits(env, previous, "nothing")
    head, before = repo.git("rev-parse", "HEAD", cwd=part), len(env.review_calls())
    (part / "use.py").write_text("B_VALUE = 2\n", "utf-8")

    closed = env.close("STACK/B")
    assert closed.returncode != 0, closed.stdout + closed.stderr
    assert (part / "use.py").read_text("utf-8") == "B_VALUE = 2\n"
    assert repo.git("rev-parse", "HEAD", cwd=part) == head
    assert len(env.review_calls()) == before
