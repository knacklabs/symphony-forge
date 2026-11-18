"""forge doctor reads finished work pull requests in a batch."""
from __future__ import annotations

import copy
import json
import re

import pytest

from test_ci_time_report import _doctor_history, _graphql
from test_close import env as doctor_env
from test_doctor_fix import _client, _prs, _work

pytestmark = pytest.mark.platform
STORY = "next-and-doctor-speed"


def test_3_doctor_batches_finished_pull_request_reads(repo, gh, tmp_path):
    _client(repo)
    first, first_head = _work(repo, tmp_path, "fix/first")
    second, second_head = _work(repo, tmp_path, "story/second")
    _prs(gh, "fix/first", (first_head, "MERGED"))
    _prs(gh, "story/second", (second_head, "CLOSED"))

    done = repo.forge("doctor")

    assert "2 folders hold finished work" in done.stdout
    assert str(first) in done.stdout and str(second) in done.stdout
    calls = [call for call in gh.calls() if call[:2] == ["api", "graphql"]
             and any(arg.startswith("query=") and "worktree_" in arg for arg in call)]
    assert len(calls) == 1
    query = next(arg[6:] for arg in calls[0] if arg.startswith("query=") and "worktree_" in arg)
    assert re.search(r'headRefName\s*:\s*"fix/first"', query)
    assert re.search(r'headRefName\s*:\s*"story/second"', query)


def test_4_doctor_batches_ci_history_and_check_reads(doctor_env):
    durations = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 11,
                 9, 9, 9, 9, 9, 9, 9, 9, 9]
    history = _doctor_history(durations)
    for pr in history:
        last = pr["commits"]["nodes"][-1]
        pr["commits"]["nodes"] = [copy.deepcopy(last) for _ in range(5)]
        for index, node in enumerate(pr["commits"]["nodes"]):
            node["commit"]["oid"] = f'push-{pr["number"]}-{index}'
    _graphql(doctor_env, history)

    done = doctor_env.repo.forge("doctor")

    assert "last 20 merged pull requests is 11 min" in done.stdout, done.stdout + repr(doctor_env.gh.calls())
    queries = [next(arg[6:] for arg in call if arg.startswith("query="))
               for call in doctor_env.gh.calls() if call[:2] == ["api", "graphql"]
               and any(arg.startswith("query=") for arg in call)]
    history_queries = [query for query in queries if "states:MERGED" in query and "statusCheckRollup" in query]
    check_queries = [query for query in queries if "nodes(ids:" in query and "checkRuns" in query]
    assert len(history_queries) == 1
    assert len(check_queries) == 1
    ids = re.findall(r"nodes\(ids:\s*(\[[^]]+\])\)", check_queries[0])
    assert len({commit for group in ids for commit in json.loads(group)}) == 100
