"""forge doctor reads finished work pull requests in a batch."""
from __future__ import annotations

import copy
import json
import re

import pytest

from test_ci_time_report import _doctor_history, _graphql, _recent_pushes
from test_close import env as doctor_env
from test_doctor_fix import _client, _prs, _work

pytestmark = pytest.mark.platform
STORY = "next-and-doctor-speed"


def test_3_doctor_batches_finished_pull_request_reads(repo, gh, tmp_path):
    _client(repo)
    first, first_head = _work(repo, tmp_path, "fix/first")
    second, second_head = _work(repo, tmp_path, "story/second")
    files_branch = "fix/forge-files-20261004-0900"
    _, files_head = _work(repo, tmp_path, files_branch)
    closed_files = [f"fix/forge-files-2026100{day}-0900" for day in (1, 2, 3)]
    _prs(gh, "fix/first", (first_head, "MERGED"))
    _prs(gh, "story/second", (second_head, "CLOSED"))
    _prs(gh, files_branch, (files_head, "OPEN"))
    for branch in closed_files:
        repo.git("branch", branch)
        _prs(gh, branch, (repo.git("rev-parse", branch), "CLOSED"))

    done = repo.forge("doctor")

    assert "2 folders hold finished work" in done.stdout
    assert str(first) in done.stdout and str(second) in done.stdout
    calls = [call for call in gh.calls() if call[:2] == ["api", "graphql"]
             and any(arg.startswith("query=") and "fix/first" in arg and "story/second" in arg for arg in call)]
    assert len(calls) == 1
    query = next(arg[6:] for arg in calls[0] if arg.startswith("query=") and "worktree_" in arg)
    assert re.search(r'headRefName\s*:\s*"fix/first"', query)
    assert re.search(r'headRefName\s*:\s*"story/second"', query)

    before = len(gh.calls())
    fixed = repo.forge("doctor", "--fix")
    assert "Doctor's fix forge-files-20261004-0900 isn't merged yet" in fixed.stdout
    calls = [call for call in gh.calls()[before:] if call[:2] == ["api", "graphql"]
             and any(arg.startswith("query=") and all(branch in arg for branch in [files_branch, *closed_files])
                     for arg in call)]
    assert len(calls) == 1
    query = next(arg[6:] for arg in calls[0] if arg.startswith("query=") and files_branch in arg)
    assert re.search(r'headRefName\s*:\s*"fix/forge-files-20261004-0900"', query)
    assert "orderBy:{field:CREATED_AT,direction:DESC}" in query
    assert not any(call[:4] == ["pr", "list", "--head", branch]
                   for call in gh.calls()[before:] for branch in [files_branch, *closed_files])


def test_4_doctor_batches_ci_history_and_check_reads(doctor_env, monkeypatch):
    monkeypatch.setenv("FORGE_NOW", "2026-11-19T08:00:00+00:00")
    _recent_pushes(doctor_env)
    durations = [20, 19, 18, 17, 16, 15, 14, 13, 12, 11, 11,
                 9, 9, 9, 9, 9, 9, 9, 9, 9]
    history = _doctor_history(durations)
    for pr in history:
        last = pr["commits"]["nodes"][-1]
        pr["commits"]["nodes"] = [copy.deepcopy(last) for _ in range(5)]
        for index, node in enumerate(pr["commits"]["nodes"]):
            node["commit"]["oid"] = f'push-{pr["number"]}-{index}'
    for node, node_id in zip(history[0]["commits"]["nodes"],
                             ("commit-7-0", "commit-7-3", "commit-7-4", "commit-7-5", "commit-7-6")):
        node["commit"]["id"] = node_id
    _graphql(doctor_env, history)

    calls_before = len(doctor_env.gh.calls())
    done = doctor_env.repo.forge("doctor")

    assert "last 20 merged pull requests is 11 min" in done.stdout, done.stdout + repr(doctor_env.gh.calls())
    queries = [next(arg[6:] for arg in call if arg.startswith("query="))
               for call in doctor_env.gh.calls()[calls_before:] if call[:2] == ["api", "graphql"]
               and any(arg.startswith("query=") for arg in call)]
    history_queries = [query for query in queries if "states:MERGED" in query and "statusCheckRollup" in query]
    check_queries = [query for query in queries if "nodes(ids:" in query and "checkRuns" in query]
    assert len(history_queries) == 1
    assert len(check_queries) == 1
    ids = re.findall(r"nodes\(ids:\s*(\[[^]]+\])\)", check_queries[0])
    assert len({commit for group in ids for commit in json.loads(group)}) == 95

    warm_before = len(doctor_env.gh.calls())
    monkeypatch.setenv("FORGE_NOW", "2026-11-19T08:00:59+00:00")
    warm = doctor_env.repo.forge("doctor")
    assert "last 20 merged pull requests is 11 min" in warm.stdout
    assert not [call for call in doctor_env.gh.calls()[warm_before:] if call[:2] == ["api", "graphql"]
                and any(arg.startswith("query=") and "nodes(ids:" in arg and "checkRuns" in arg for arg in call)]

    refresh_before = len(doctor_env.gh.calls())
    changed = copy.deepcopy(history)
    changed[0]["commits"]["nodes"][0]["commit"]["id"] = "new-push-head"
    _graphql(doctor_env, changed)
    refresh = doctor_env.repo.forge("doctor")
    assert "last 20 merged pull requests is 11 min" in refresh.stdout
    refresh_queries = [next(arg[6:] for arg in call if arg.startswith("query="))
                       for call in doctor_env.gh.calls()[refresh_before:] if call[:2] == ["api", "graphql"]
                       and any(arg.startswith("query=") and "nodes(ids:" in arg and "checkRuns" in arg for arg in call)]
    [refresh_query] = refresh_queries
    new_ids = re.findall(r"nodes\(ids:\s*(\[[^]]+\])\)", refresh_query)
    assert {commit for group in new_ids for commit in json.loads(group)} == {"new-push-head"}

    expired_before = len(doctor_env.gh.calls())
    monkeypatch.setenv("FORGE_NOW", "2026-11-19T08:01:00+00:00")
    expired = doctor_env.repo.forge("doctor")
    assert "last 20 merged pull requests is 11 min" in expired.stdout
    expired_queries = [next(arg[6:] for arg in call if arg.startswith("query="))
                       for call in doctor_env.gh.calls()[expired_before:] if call[:2] == ["api", "graphql"]
                       and any(arg.startswith("query=") and "nodes(ids:" in arg and "checkRuns" in arg for arg in call)]
    [expired_query] = expired_queries
    expired_ids = re.findall(r"nodes\(ids:\s*(\[[^]]+\])\)", expired_query)
    assert len({commit for group in expired_ids for commit in json.loads(group)}) == 99
