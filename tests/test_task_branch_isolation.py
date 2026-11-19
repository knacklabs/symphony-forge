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


@pytest.mark.parametrize("old_stack", [False, True], ids=["accidental-merge", "earlier-stacked-start"])
def test_2_close_names_other_open_task_commits(env, old_stack):
    repo = configured(env)
    first_path = reviewed(env)
    story(repo, doc=DOC, approved=DOC, key="SECOND")
    second = repo.forge("task", "start", "SECOND/E")
    assert second.returncode == 0, second.stdout + second.stderr
    second_path = Path(second.stdout.splitlines()[0].rsplit(" in ", 1)[1])
    env.commit(second_path, "other.py", "SECOND_VALUE = 2\n")
    repo.git("merge", "-q", "--no-edit", "task/STACK-A", cwd=second_path)
    if old_stack:
        rel = ".factory/stories/SECOND/tasks/E.json"
        state = json.loads((second_path / rel).read_text("utf-8"))
        state.update(stacked_on="STACK/A", base=repo.git("rev-parse", "HEAD", cwd=first_path))
        env.commit(second_path, rel, json.dumps(state), "Keep the earlier stacked start")
    closed = env.close("SECOND/E")
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "SECOND/E includes unmerged commits from STACK/A." in closed.stderr
    assert "Next: forge work SECOND/E" in closed.stderr
