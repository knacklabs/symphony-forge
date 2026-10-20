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
    history.at(NOW)
    repo.git("push", "-q", "origin", "main")
    repo.git("tag", "v0.1.0")
    repo.git("push", "-q", "origin", "--tags")
    history.publish()
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
    again = up.run(RELEASE)
    assert again.returncode == 0, again.stdout + again.stderr
    assert history.stored() == before
    failure.touch()
    monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(days=2)).isoformat())
    offline = rows(board(repo))
    assert board(repo)["known_issues"] == [issue]
    for item in ("SHOP", "SHOP/T1", "SHOP/T2"):
        for field in ("started_by", "started_by_login", "developer", "developer_login", "released_in"):
            assert offline[item][field] == first[item][field]
