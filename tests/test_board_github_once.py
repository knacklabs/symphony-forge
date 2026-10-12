"""The board reads GitHub's pull request lists at most once a minute, one search per week.

Only GitHub is a stub; the case reads the calls it got and the board's JSON. It runs as a case
of criterion 1's test in test_board_counts.py, since one rule has one test.
"""
import json
from datetime import datetime, timedelta, timezone

from test_close_keeps_reviews_for_unchanged_branch_diffs import client


def lists(env):
    return [call for call in env.gh_calls("pr", "list") if "--head" not in call]


def github_read_once(env, monkeypatch, previous):
    """Two boards in a minute make one open list and one search per week."""
    client(env, previous)
    now = datetime(2026, 10, 14, 15, tzinfo=timezone.utc)  # a Wednesday
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    env.gh.respond("pr", "list", stdout="[]")
    before = len(lists(env))
    for _ in range(2):
        shown = env.repo.forge("board", "--json")
        assert shown.returncode == 0, shown.stderr
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
        assert json.loads(shown.stdout)["team"]["counts"]["fixes"]
    assert len(lists(env)) - before == 8 + 2
