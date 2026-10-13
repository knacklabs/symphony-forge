"""The team and each person show merged pull requests per week, through and around Forge.

Only GitHub is a stub; board output is all the test reads.
"""
from datetime import datetime, timedelta, timezone

import pytest

from test_board_counts import board, github
from test_close import env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FORGE-BOARD-2"

ANA = {"login": "ana", "name": "ana Silva"}
BEN = {"login": "ben", "name": "Ben Ode"}
NO_NAME = {"login": "cara-dev"}
OTHER_BEN = {"login": "ben-o", "name": "Ben Ode"}


def pr(number, branch, author, at, title="A change"):
    return {"number": number, "headRefName": branch, "state": "MERGED", "title": title, "body": "",
            "isDraft": False, "mergedAt": at.isoformat(), "mergedBy": {"login": "ana"}, "author": author,
            "url": f"https://github.com/acme/shop/pull/{number}"}


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_6_weekly_trends_through_and_around_forge_and_this_weeks_around_list(env, monkeypatch, previous):
    client(env, previous)
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    today = now.date()
    monday = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=today.weekday())
    weeks = [monday - timedelta(weeks=n) for n in range(6, 0, -1)]
    day = lambda week, hours=12: weeks[week] + timedelta(days=2, hours=hours)  # noqa: E731
    recent = now - timedelta(hours=1)
    prs = [pr(1, "task/SHOP-T1", BEN, day(0)), pr(2, "hotfix-login", BEN, day(0)),
           pr(3, "fix/readme", ANA, day(1)), pr(4, "story/SHOP", NO_NAME, day(3)),
           pr(5, "main-tweak", NO_NAME, day(5)), pr(6, "fix/typo", ANA, day(5)),
           pr(7, "quick-patch", ANA, recent, "Patch the login page"), pr(8, "fix/menu", OTHER_BEN, day(4))]
    github(env, prs)
    team = board(env.repo)["team"]
    zero = {"through": 0, "around": 0}
    assert team["trends"] == {
        "weeks": [w.date().isoformat() for w in weeks],
        "team": [{"through": 1, "around": 1}, {"through": 1, "around": 0}, zero, {"through": 1, "around": 0},
                 {"through": 1, "around": 0}, {"through": 1, "around": 1}],
        # Alphabetical ignoring case, by name or login without one; no totals or ranks.
        "people": [{"name": "ana Silva", "weeks": [zero, {"through": 1, "around": 0}, zero, zero, zero,
                                                  {"through": 1, "around": 0}]},
                   # Two people sharing a name stay apart, told apart by their login.
                   {"name": "Ben Ode", "weeks": [{"through": 1, "around": 1}, zero, zero, zero, zero, zero]},
                   {"name": "Ben Ode", "weeks": [zero, zero, zero, zero, {"through": 1, "around": 0}, zero]},
                   {"name": "cara-dev", "weeks": [zero, zero, zero, {"through": 1, "around": 0}, zero,
                                                 {"through": 0, "around": 1}]}]}
    expected = [{"title": "Patch the login page", "author": "ana Silva", "merged_at": recent.isoformat(),
                 "url": "https://github.com/acme/shop/pull/7"}]
    if now - day(5) <= timedelta(weeks=1):
        expected.append({"title": "A change", "author": "cara-dev", "merged_at": day(5).isoformat(),
                         "url": "https://github.com/acme/shop/pull/5"})
    assert team["around_forge"] == expected

    # A week whose search hits GitHub's cap is unknown; the other weeks stay known.
    capped = [pr(100 + n, f"bulk-{n}", BEN, day(2)) for n in range(1000)]
    github(env, prs + capped)
    monkeypatch.setenv("FORGE_NOW", (now + timedelta(minutes=2)).isoformat())
    trends = board(env.repo)["team"]["trends"]
    assert trends["team"][2] is None and trends["team"][0] == {"through": 1, "around": 1}
    assert all(person["weeks"][2] is None for person in trends["people"])
