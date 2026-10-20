"""Upgrade recovers past identities before the board needs GitHub.

Audit (test-audit): older PRs lose logins outside the runway; different names
also expose task rows replacing the shared resolver. Existing login tests use
recent PRs. Real upgrade, git, plans, tags and board JSON own the assertions;
only GitHub and the release installer/reviewer are faked. No production seam.
"""
from datetime import timedelta
import json

import pytest

from test_board_after_upgrade import History, NOW
from test_board_counts import board, rows
from test_close import env  # noqa: F401
from test_story import worktree
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-BOARD-3"


@pytest.mark.parametrize("outage", [False, True], ids=["reachable", "retry-on-close"])
def test_6_upgrade_fills_past_people_owners_issues_and_releases(unsynced_up, monkeypatch, outage):
    history = History(unsynced_up, monkeypatch)
    repo, up = history.repo, history.up
    history.story()
    plan = (repo.path / "plans/SHOP.md").read_text("utf-8")
    plan = plan.replace("| User-facing |", "| User-facing | Developer |")
    plan = plan.replace("| yes |", "| yes | merger |")
    plan = plan.replace("| no |", "| no | merger |")
    plan += "\nOwner: starter\n"
    history.commit(repo.path, "plans/SHOP.md", plan, "Record the owners", NOW - timedelta(days=95))
    repo.git("merge", "-q", "--ff-only", "main", cwd=worktree(repo, "story/SHOP"))
    repo.git("push", "-q", "origin", "story/SHOP")
    history.item("past-first", 31, 90, task="T1")
    history.item("past-second", 32, 80, task="T2")
    history.prs[1]["author"]["name"] = "Another Starter Name"
    history.prs[1]["mergedBy"] = {"login": "merger"}
    # The retained problem survives only in the original pull ref, not the squash.
    original = up.tmp / "original-review"
    repo.git("worktree", "add", "-q", "--detach", original.as_posix(), history.prs[0]["headRefOid"])
    path = ".factory/stories/SHOP/tasks/T1.json"
    state = json.loads((original / path).read_text("utf-8"))
    state["known"] = [{"file": "past-first.py", "line": 1, "title": "Add a greeting example",
                       "gain": 3, "work": 4, "harm": 2, "outcome": "follow-up",
                       "reason": "Keep this for the next help change"}]
    head = history.commit(original, path, json.dumps(state), "Keep the review decision", NOW - timedelta(days=90))
    repo.git("push", "-q", "origin", head + ":refs/pull/31/head")
    repo.git("worktree", "remove", original.as_posix())
    history.prs[0]["headRefOid"] = head
    history.item("recent-people", 33, 10)
    history.at(NOW)
    repo.git("push", "-q", "origin", "main")
    repo.git("tag", "v0.1.0")
    repo.git("push", "-q", "origin", "--tags")
    history.publish()
    # gh.cmd cannot carry a literal line break in an argument. Enforce that
    # external transport contract on every platform, through the real upgrade.
    (repo.bin / "batch-launcher").touch()
    failure = repo.bin / "history-unreachable"
    if outage:
        failure.touch()
    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    if outage:
        failure.unlink()
        retried = repo.forge("close", "upgrade-forge-to-v9-9-9", cwd=up.folder)
        assert retried.returncode == 0, retried.stdout + retried.stderr
    failure.touch()  # Upgrade must fill the facts before the first board read.
    shown = board(repo)
    first = rows(shown)
    [issue] = shown["known_issues"]
    assert issue == {"item": "SHOP/T1", "file": "past-first.py", "line": 1,
                     "title": "Add a greeting example", "gain": 3, "work": 4, "harm": 2,
                     "kept": "follow-up", "reason": "Keep this for the next help change"}
    for item in ("SHOP/T1", "SHOP/T2"):
        assert first[item]["started_by_login"] == "starter"
        assert first[item]["developer_login"] == "merger"
        assert first[item]["approved_by_login"] is None
    assert first["SHOP/T1"]["started_by"] == first["SHOP/T2"]["started_by"]
    assert first["SHOP"]["developer"] == first["SHOP/T1"]["started_by"]
    assert first["SHOP/T1"]["developer"] == first["SHOP/T2"]["developer"] == "Human Merger"
    assert first["SHOP/T1"]["released_in"] == first["SHOP/T2"]["released_in"] == "v0.1.0"
    before = history.stored()
    failure.unlink()
    # A later GitHub response can omit an actor. The recorded login still holds.
    store = repo.bin / "historical-prs.json"
    refreshed = list(before.values())
    for pr in refreshed:
        if pr["number"] == 33:
            pr.update(author=None, mergedBy=None)
    store.write_text(json.dumps(refreshed), "utf-8")
    monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(seconds=121)).isoformat())
    refreshed_people = rows(board(repo))["recent-people"]
    assert refreshed_people["started_by_login"] == "starter"
    assert refreshed_people["merged_by"] == {"name": "Human Merger", "login": "merger"}
    before = history.stored()
    again = up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    assert history.stored() == before
    failure.touch()
    monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(days=2)).isoformat())
    offline = rows(board(repo))
    assert board(repo)["known_issues"] == [issue]
    for item in ("SHOP", "SHOP/T1", "SHOP/T2", "recent-people"):
        for field in ("started_by", "started_by_login", "developer", "developer_login", "released_in"):
            assert offline[item][field] == first[item][field]


def test_15_upgrade_preserves_published_times_when_a_part_ages_out(unsynced_up, monkeypatch):
    """The real first upgrade publishes CI history from GitHub's check times.
    Later upgrades must retain it after the part leaves the recent PR window.
    No local worker or check logs supply this part's recorded time.
    """
    history = History(unsynced_up, monkeypatch)
    history.story()
    history.item("older-part", 31, 21, task="T1")
    history.publish()
    up, repo = history.up, history.repo
    first = up.run(RELEASE)
    assert first.returncode == 0, first.stdout + first.stderr
    assert history.record(31), "The first upgrade must publish the original check history"
    before = rows(board(repo))
    assert before["SHOP/T1"]["waiting_seconds"] > 0
    assert before["SHOP"]["waiting_seconds"] >= before["SHOP/T1"]["waiting_seconds"]
    history.at(NOW + timedelta(days=70))
    again = up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    after = rows(board(repo))
    assert after["SHOP/T1"]["started_by_login"] == "starter"
    for item in ("SHOP", "SHOP/T1"):
        for field in ("working_seconds", "waiting_seconds"):
            assert after[item][field] == before[item][field], (item, field, before[item], after[item])
    assert after["SHOP/T1"]["rounds"] == before["SHOP/T1"]["rounds"]
