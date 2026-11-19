"""Tasks of separate stories keep separate unmerged work."""
from pathlib import Path
import json

import pytest

from test_close import env  # noqa: F401
from test_stack_start import DOC, configured, reviewed
from test_task import story

STORY = "FIX-TASK-START-WRONG-BASE"


def test_1_task_start_keeps_other_story_commits_out(env):
    repo = configured(env)
    first_path = reviewed(env)
    foreign = repo.git("rev-parse", "HEAD", cwd=first_path)
    story(repo, doc=DOC, approved=DOC, key="SECOND")
    # Incidental Scope overlap is not permission to take another story's history.
    refused = repo.forge("task", "start", "SECOND/A", cwd=first_path)
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "STACK/A" in refused.stderr and "hasn't merged yet" in refused.stderr
    assert not repo.git("branch", "--list", "task/SECOND-A")
    second = repo.forge("task", "start", "SECOND/E", cwd=first_path)
    assert second.returncode == 0, second.stdout + second.stderr
    second_path = Path(second.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    assert foreign not in repo.git("rev-list", "HEAD", cwd=second_path).splitlines()
    assert not (second_path / "app.py").exists()


@pytest.mark.parametrize("case", ["merge", "old-stack", "cherry-pick", "later-parent", "revert"])
def test_2_close_names_other_open_task_commits(env, case):
    env.commit(env.repo.path, "foreign.py", "ORIGINAL_VALUE = 1\n")
    repo = configured(env)
    first_path = reviewed(env)
    if case != "later-parent":
        story(repo, doc=DOC, approved=DOC, key="SECOND")
    item = "STACK/B" if case == "later-parent" else "SECOND/E"
    second = repo.forge("task", "start", item)
    assert second.returncode == 0, second.stdout + second.stderr
    second_path = Path(second.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(second_path, "other.py", "SECOND_VALUE = 2\n")
    foreign = env.commit(first_path, "foreign.py", "FOREIGN_VALUE = 2\n")
    if case in ("cherry-pick", "later-parent"):
        repo.git("cherry-pick", foreign, cwd=second_path)
    else:
        repo.git("merge", "-q", "--no-edit", "task/STACK-A", cwd=second_path)
    if case == "old-stack":
        rel = ".factory/stories/SECOND/tasks/E.json"
        state = json.loads((second_path / rel).read_text("utf-8"))
        state.update(stacked_on="STACK/A", base=repo.git("rev-parse", "HEAD", cwd=first_path))
        env.commit(second_path, rel, json.dumps(state), "Keep the earlier stacked start")
    if case == "revert":
        repo.git("revert", "--no-edit", "-m", "1", "HEAD", cwd=second_path)
        # An independent edit of the same file must not revive the reverted import.
        env.commit(second_path, "foreign.py", "SECOND_VALUE = 3\n")
    closed = env.close(item)
    if case == "revert":
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert f"Ready: {item}" in closed.stdout
        return
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert f"{item} includes unmerged commits from STACK/A." in closed.stderr
    assert "Remove or revert those changes before close." in closed.stderr
    assert f"Next: forge work {item}" in closed.stderr


def test_3_start_names_every_overlapping_task(env):
    repo = configured(env)
    reviewed(env)
    story(repo, doc=DOC, approved=DOC, key="SECOND")
    second = repo.forge("task", "start", "SECOND/E")
    assert second.returncode == 0, second.stdout + second.stderr
    wider = DOC.replace("| `app.py` | `tests/test_work.py` | A |", "| `app.py`, `other.py` | `tests/test_work.py` | A |")
    story(repo, doc=wider, approved=DOC, key="STACK")
    refused = repo.forge("task", "start", "STACK/C")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert ("STACK/C has open blockers: STACK/A, SECOND/E. Parts of another story must merge first."
            in refused.stderr)
    assert not repo.git("branch", "--list", "task/STACK-C")
    # Once the foreign blocker merges, the reviewed own-story base remains usable.
    repo.git("merge", "-q", "--no-edit", "task/SECOND-E")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("task", "start", "STACK/C")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "on top of STACK/A" in started.stdout
