"""The board reads GitHub's pull request lists at most once a minute, one search per week.

Only GitHub is a stub; the case reads the calls it got and the board's JSON. It runs as a case
of criterion 1's test in test_board_counts.py, since one rule has one test.
"""
import json
from datetime import datetime, timedelta, timezone

from test_close_keeps_reviews_for_unchanged_branch_diffs import client


def row(data, item):
    return next(r for r in data["items"] if r["id"] == item)


def lists(env):
    return [call for call in env.gh_calls("pr", "list") if "--head" not in call]


def github_read_once(env, monkeypatch, previous):
    """Two boards in a minute make one open list and one search per week."""
    client(env, previous)
    now = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)  # a Wednesday
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    item, _ = env.start_fix()
    env.gh.respond("pr", "list", stdout=json.dumps([{
        "number": 7, "headRefName": f"fix/{item}", "state": "OPEN", "title": "Readme greets new readers",
        "body": "", "isDraft": False, "url": "https://github.com/acme/shop/pull/7"}]))
    before = len(lists(env))
    for _ in range(2):
        shown = env.repo.forge("board", "--json")
        assert shown.returncode == 0, shown.stderr
    assert row(json.loads(shown.stdout), item)["pr"]["number"] == 7
    calls = lists(env)[before:]
    assert [call[call.index("--state") + 1] for call in calls] == ["open"] + ["merged"] * 7
    monday = datetime(2026, 10, 12, tzinfo=timezone.utc)
    weeks = [monday - timedelta(weeks=n) for n in range(6, -1, -1)]
    assert [call[call.index("--search") + 1] for call in calls[1:]] == [
        f"merged:{start:%Y-%m-%d}..{start + timedelta(days=6):%Y-%m-%d}" for start in weeks]

    # A minute later GitHub is asked again; a failed answer still prints the board and is not kept.
    monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=61)).isoformat())
    env.gh.respond("pr", "list", exit=1, stderr="GitHub is unavailable\n")
    for _ in range(2):
        shown = env.repo.forge("board", "--json")
        assert shown.returncode == 0, shown.stderr
        data = json.loads(shown.stdout)
        assert data["team"]["counts"]["fixes"]["in progress"] == 1
        # What only GitHub knows is unknown: the pull request, who merged it and the trends.
        assert row(data, item)["pr"]["number"] is None and row(data, item)["merged_by"] is None
        assert all(data["team"][key] is None for key in ("pace", "go_live", "trends", "around_forge"))
    assert len(lists(env)) - before == 8 + 2
