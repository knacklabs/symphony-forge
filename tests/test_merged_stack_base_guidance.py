"""Stale-base guidance must name a command that makes the next start work.

Test-audit: The old refusal reports a completed merge. Existing tests manually
rebase instead of following its advice. Real commands own this journey, with
only GitHub and review services replaced. No production test seam is needed.
"""
import json
import sys

import pytest

from conftest import GH_STUB, _install
from test_close import env  # noqa: F401
from test_last_task_records_story_outcome import github_merge
from test_stack_close import _stacked_pair
from test_stack_start import start

STORY = "FIX-WAITING-PART-NAMES-A-MERGED-PART"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_merged_dependency_names_close_and_close_allows_start(env, previous):
    repo, _ = _stacked_pair(env, previous)
    env.gh.respond("pr", "list", "--base", "task/STACK-A", stdout=json.dumps([
        {"number": 8, "headRefName": "task/STACK-B"},
    ]))
    github_merge(env, "task/STACK-A")
    merged = repo.forge("merge", "STACK/A")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    problem = "STACK/D waits for STACK/B to include the merge of STACK/A from main."
    command = "forge close STACK/B"
    refused = repo.forge("task", "start", "STACK/D")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert refused.stderr == f"{problem}\nNext: {command}\n"
    for args in (("next",), ("board", "--json")):
        shown = repo.forge(*args)
        assert shown.returncode == 0, shown.stdout + shown.stderr
        output = shown.stdout if args[0] == "next" else json.dumps(json.loads(shown.stdout))
        if args[0] == "next":
            assert problem in output
        assert "so it starts once STACK/A merges" not in output
        assert command in output
    _install(repo.bin, "gh", GH_STUB.format(python=sys.executable))
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all",
                   stdout=json.dumps([{"number": 8, "state": "OPEN", "body": "",
                                       "isDraft": False, "baseRefName": "main"}]))
    closed = repo.forge(*command.split()[1:])
    assert closed.returncode == 0, closed.stdout + closed.stderr
    where, _ = start(repo, "D")
    repo.git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=where)
    assert (where / "use.py").read_text("utf-8") == "B_VALUE = 1\n"
