"""Pace counts merged parts and fixes per full week; go-live turns it into a date range.

Real Forge commands and git build every item; merged work lands on main with set commit dates.
Board output is all the test reads.
"""
import json
from datetime import datetime, timedelta, timezone

import pytest

from test_board_counts import ONE_PART, PLAN, board, configure
from test_close import approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FORGE-BOARD-2"

SIX_PARTS = PLAN.replace(
    "| T4 | Empty a basket | A shopper can empty a basket | 2 | `empty.py` | `tests/test_empty.py` | — | no |",
    "| T4 | Empty a basket | A shopper can empty a basket | 2 | `empty.py` | `tests/test_empty.py` | — | no |\n"
    "| T5 | Name a basket | A shopper can name a basket | 2 | `name.py` | `tests/test_name.py` | — | no |\n"
    "| T6 | Copy a basket | A shopper can copy a basket | 2 | `copy.py` | `tests/test_copy.py` | — | no |")
NO_PLAN = "Shoppers can buy gift cards"
IDLE = "0 stories building, 0 parts and fixes in progress, 0 ready to merge; "


def merged(env, monkeypatch, at, rel, state):
    """A part or fix lands on main at `at`."""
    for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.setenv(name, at.isoformat())
    env.commit(env.repo.path, rel, json.dumps(state), "Merge finished work")
    env.repo.git("push", "-q", "origin", "main")
    for name in ("GIT_AUTHOR_DATE", "GIT_COMMITTER_DATE"):
        monkeypatch.delenv(name)


def parts_per_week(env, monkeypatch, weeks, counts, first=0):
    for start, count in zip(weeks, counts):
        for n in range(count):
            first += 1
            merged(env, monkeypatch, start + timedelta(days=1, hours=n),
                   f".factory/stories/OLD/tasks/P{first}.json", {"kind": "task", "status": "merged"})
    return first


def go_live(env):
    team = board(env.repo)["team"]
    assert team["go_live"]["no_plan"] == {"count": 1, "titles": [NO_PLAN]}
    assert f"unknown, with no plan yet: {NO_PLAN}" in team["sentence"]
    return team


@pytest.mark.parametrize("case", ["range", "about"])
@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_4_pace_and_go_live_from_the_last_three_and_six_weeks(env, monkeypatch, previous, case):
    client(env, previous)
    configure(env, "agent")
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    today = now.date()
    monday = datetime(today.year, today.month, today.day, tzinfo=timezone.utc) - timedelta(days=today.weekday())
    weeks = [monday - timedelta(weeks=n) for n in range(6, 0, -1)]
    roadmap = env.repo.path / "plans" / "roadmap.json"
    env.commit(env.repo.path, "plans/roadmap.json", json.dumps({"items": [
        *(json.loads(roadmap.read_text("utf-8"))["items"] if roadmap.exists() else []),
        {"key": "GIFT", "title": NO_PLAN}]}), "Plan gift cards later")
    env.commit(env.repo.path, ".factory/stories/OLD/story.json", '{"status": "done"}', "An older story is done")
    env.repo.git("push", "-q", "origin", "main")

    if case == "about":
        parts_per_week(env, monkeypatch, weeks, [1] * 6)
        approve_story(env.repo, ONE_PART)
        team = go_live(env)
        due = (today + timedelta(days=7)).isoformat()
        assert team["go_live"] == {"status": "about", "earliest": due, "latest": due, "remaining_parts": 1,
                                   "no_plan": team["go_live"]["no_plan"]}
        assert "the two pace estimates agree" in team["sentence"]
        return

    # A fresh repo with nothing planned has no history to go on.
    team = go_live(env)
    assert team["go_live"]["status"] == "not enough history" and team["go_live"]["remaining_parts"] == 0
    assert team["sentence"].startswith(IDLE + "not enough history to estimate go-live")
    assert [week["week_start"] for week in team["pace"]["weeks"]] == [w.date().isoformat() for w in weeks]

    # Two weeks of merges are not enough either.
    first = parts_per_week(env, monkeypatch, weeks[4:], [1, 0])
    assert go_live(env)["go_live"]["status"] == "not enough history"

    # Six weeks of merges and nothing left: planned work is done. A fix counts apart; a story's
    # done record is no fix.
    parts_per_week(env, monkeypatch, weeks[:4], [4, 2, 2, 1], first)
    merged(env, monkeypatch, weeks[2] + timedelta(days=2), ".factory/fixes/readme.json", {"kind": "fix"})
    merged(env, monkeypatch, weeks[2] + timedelta(days=3), ".factory/fixes/old-done.json", {"kind": "story-done"})
    team = go_live(env)
    assert team["pace"] == {"weeks": [{"week_start": w.date().isoformat(), "parts": parts, "fixes": fixes}
                                      for w, parts, fixes in zip(weeks, [4, 2, 2, 1, 1, 0], [0, 0, 1, 0, 0, 0])],
                            "parts_per_week_3": 0.67, "parts_per_week_6": 1.67}
    assert team["go_live"]["status"] == "done" and team["sentence"].startswith(IDLE + "planned work is done")

    # Six parts left: 6 / (2/3) weeks and 6 / (10/6) weeks from today.
    approve_story(env.repo, SIX_PARTS)
    team = go_live(env)
    assert team["go_live"] == {"status": "range", "earliest": (today + timedelta(days=26)).isoformat(),
                               "latest": (today + timedelta(days=63)).isoformat(), "remaining_parts": 6,
                               "no_plan": team["go_live"]["no_plan"]}
    assert team["sentence"].startswith(IDLE + "planned work can go live between")
