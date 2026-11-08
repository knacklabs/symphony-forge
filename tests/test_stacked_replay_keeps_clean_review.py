"""Close reuses a stacked review only while its reviewed diff stays unchanged."""

import json
import subprocess

import pytest

from test_close import env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_stack_close import _stacked_pair

STORY = "keep-review-on-same-replay"


@pytest.mark.parametrize("previous,scenario", [(False, "unchanged"), (False, "changed"),
                                              (True, "unchanged"), (False, "merge-edits"),
                                              (False, "same-diff-conflict")],
                         ids=["unchanged-new", "changed-new", "unchanged-previously-adopted",
                              "reviewed-merge-edits", "same-diff-conflict"])
def test_1_close_keeps_clean_review_only_for_identical_stacked_content(env, previous, scenario):
    # Audit: restoration can lose worker evidence; a conflict can retain identical
    # diff bytes. Ordinary replay and changed-diff conflict cases cannot expose either.
    # Exercise close and real Git merges, with no production-only testing seam.
    repo, _ = _stacked_pair(env, previous)
    where = repo.path.parent / f"{repo.path.name}-STACK-B"
    if scenario == "merge-edits":
        env.commit(where, "use.py", "B_VALUE = 2\n", "Build the child\n\n"
                   "Functional check: Read the child value.\n\nProof list: Check the child.")
        env.commit(repo.path, "notes.txt", "An unrelated default update.\n")
        repo.git("push", "-q", "origin", "main")
        repo.git("merge", "-q", "--no-commit", "origin/main", cwd=where)
        env.commit(where, "merge-edit.py", "MERGED_VALUE = 1\n", "Include a merge edit")
    elif scenario == "same-diff-conflict":
        env.commit(where, "app.py", "A_VALUE = 2\n", "Use the child value")
    if scenario in {"merge-edits", "same-diff-conflict"}:
        reviewed = env.close("STACK/B")
        assert reviewed.returncode == 0, reviewed.stdout + reviewed.stderr
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
    if scenario == "changed":
        env.commit(where, "use.py", "B_VALUE = 2\n", "Change the reviewed content")
    elif scenario == "same-diff-conflict":
        merged = subprocess.run(["git", "merge", "--no-edit", "origin/main"], cwd=where,
                                capture_output=True, text=True)
        assert merged.returncode == 1, merged.stdout + merged.stderr
        assert repo.git("diff", "--name-only", "--diff-filter=U", cwd=where) == "app.py"
        env.commit(where, "app.py", "A_VALUE = 2\n", "Resolve the conflict with the child value")
    count = len(env.review_calls())
    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == count + int(scenario in {"changed", "same-diff-conflict"})
    if scenario == "merge-edits":
        assert (where / "merge-edit.py").read_text("utf-8") == "MERGED_VALUE = 1\n"
    head = repo.git("rev-parse", "origin/task/STACK-B")
    checked = repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "origin/main"),
                         "--head", head, "--branch", "task/STACK-B")
    assert checked.returncode == 0, checked.stdout + checked.stderr
