"""Close reuses a stacked review only while its reviewed diff stays unchanged."""

import json

import pytest

from test_close import env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_stack_close import _stacked_pair

STORY = "keep-review-on-same-replay"


@pytest.mark.parametrize("previous,edited", [(False, False), (False, True), (True, False)],
                         ids=["unchanged-new", "changed-new", "unchanged-previously-adopted"])
def test_1_close_keeps_clean_review_only_for_identical_stacked_content(env, previous, edited):
    repo, _ = _stacked_pair(env, previous)
    env.gh.respond("pr", "list", "--base", "task/STACK-A", stdout=json.dumps([
        {"number": 8, "headRefName": "task/STACK-B"},
    ]))
    github_merge(env, "task/STACK-A")
    merged = repo.forge("merge", "STACK/A")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    (repo.bin / "github-merged").unlink()
    github_merge(env, "task/STACK-B")
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                   stdout=json.dumps([{"number": 8, "state": "OPEN", "body": "",
                                       "isDraft": False, "baseRefName": "main"}]))
    where = repo.path.parent / f"{repo.path.name}-STACK-B"
    if edited:
        env.commit(where, "use.py", "B_VALUE = 2\n", "Change the reviewed content")
    count = len(env.review_calls())
    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == count + int(edited)
    head = repo.git("rev-parse", "origin/task/STACK-B")
    checked = repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "origin/main"),
                         "--head", head, "--branch", "task/STACK-B")
    assert checked.returncode == 0, checked.stdout + checked.stderr
