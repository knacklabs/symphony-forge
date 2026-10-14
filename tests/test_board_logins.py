"""Real board reads retain names and add known logins, including older clients.

Audit: missing login fields and name-based guesses fail at the real command.
Existing board coverage only asserts names. Only GitHub is faked; no seam is added.
"""
from datetime import datetime, timedelta, timezone

import pytest

from test_board_counts import board, github, rows
from test_board_trends import pr
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FORGE-BOARD-3"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_board_people_keep_names_and_known_github_logins(env, monkeypatch, previous):
    client(env, previous)
    env.gh.respond("api", "user", stdout="viewer-dev\n")
    env.repo.git("config", "user.name", "Plan Owner")
    env.repo.git("config", "user.email", "42+plan-owner@users.noreply.github.com")
    doc = STORY_DOC.replace("| User-facing |", "| User-facing | Developer |")
    doc = doc.replace("|---|---|---|---|---|---|---|---|", "|---|---|---|---|---|---|---|---|---|")
    doc = doc.replace("| no |", "| no | viewer-dev |").replace("| yes |", "| yes | viewer-dev |")
    approve_story(env.repo, doc)
    env.repo.git("merge", "-q", "--ff-only", "story/SHOP")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("config", "user.name", "Builder Name")
    env.repo.git("config", "user.email", "builder@example.test")
    started = env.repo.forge("task", "start", "SHOP/T1")
    assert started.returncode == 0, started.stdout + started.stderr
    head = env.repo.git("rev-parse", "task/SHOP-T1")
    env.gh.respond("api", f"repos/{{owner}}/{{repo}}/commits/{head}",
                   stdout='{"author":{"login":"builder-dev"}}')
    env.repo.git("merge", "-q", "--no-edit", "task/SHOP-T1")
    env.repo.git("push", "-q", "origin", "main")
    where = started.stdout.splitlines()[0].rsplit(" in ", 1)[1]
    env.repo.git("worktree", "remove", where)
    env.repo.git("branch", "-d", "task/SHOP-T1")
    env.repo.git("config", "user.name", "Git Only")
    env.repo.git("config", "user.email", "unknown@example.test")
    opened = env.repo.forge("fix", "start", "Keep names", "--done", "Names stay", "--slug", "names")
    assert opened.returncode == 0, opened.stdout + opened.stderr
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    monday = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
    at = monday - timedelta(days=3)
    merged = pr(1, "task/SHOP-T1", {"name": "Builder Name", "login": "builder-dev"}, now)
    merged["mergedBy"] = {"name": "Merge Owner", "login": "merge-owner"}
    github(env, [merged,
                 pr(2, "manual-a", {"name": "Same Name", "login": "first-dev"}, at),
                 pr(3, "manual-b", {"name": "Same Name", "login": "second-dev"}, at),
                 pr(4, "manual-c", {"name": "Git One"}, at),
                 pr(5, "manual-d", {"name": "Git Two"}, at)])
    data = board(env.repo)
    assert data["viewer"] == "viewer-dev"
    visible = rows(data)
    part = visible["SHOP/T1"]
    assert (part["started_by"], part["started_by_login"]) == ("Builder Name", "builder-dev")
    assert (part["approved_by"], part["approved_by_login"]) == ("Plan Owner", "plan-owner")
    assert (part["developer"], part["developer_login"]) == ("viewer-dev", "viewer-dev")
    assert part["merged_by"] == {"name": "Merge Owner", "login": "merge-owner"}
    assert visible["SHOP"]["approved_by_login"] == "plan-owner"
    assert (visible["names"]["started_by"], visible["names"]["started_by_login"]) == ("Git Only", None)
    assert visible["names"]["developer_login"] is None
    people = data["team"]["trends"]["people"]
    assert [(p["name"], p["login"]) for p in people] == [
        ("Git One", None), ("Git Two", None), ("Same Name", "first-dev"), ("Same Name", "second-dev")]
    assert all(p["weeks"][-1] == {"through": 0, "around": 1} for p in people)
    out = env.tmp / "owners.html"
    rendered = env.repo.forge("board", "--out", str(out))
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    html = out.read_text("utf-8")
    assert "Builder Name" in html and "Plan Owner" in html and "Same Name" in html
