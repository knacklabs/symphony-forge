"""Board people use loaded records and retain cached identities during outages.

Command-boundary cases cover unavailable GitHub, an actual upgrade of an earlier
client, and starter and approver identities before publication. No Forge internals
are imported and no identity lookup is faked.
"""
from datetime import datetime, timedelta, timezone
import json
import shutil
import sys

import pytest

from conftest import _install
from test_board_counts import board, github, rows
from test_board_trends import pr
from test_board_after_upgrade import History, NOW
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401
from test_story import worktree

STORY = "FORGE-BOARD-3"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_9_login_only_pull_request_keeps_the_recorded_starter_name(env, previous):
    client(env, previous)
    repo = env.repo
    repo.git("config", "user.name", "Recorded Starter")
    repo.git("config", "user.email", "starter@example.test")
    item = "recorded-starter"
    started = repo.forge("fix", "start", "Keep the starter visible", "--done", "The starter is visible", "--slug", item)
    assert started.returncode == 0, started.stdout + started.stderr
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([{
        "number": 7, "headRefName": "fix/" + item, "state": "OPEN",
        "author": {"login": "starter-dev"}, "body": ""}]))

    shown = rows(board(repo))[item]
    assert (shown["started_by"], shown["started_by_login"]) == ("Recorded Starter", "starter-dev")


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "earlier-adoption"])
def test_7_started_item_shows_its_own_starter_before_a_pull_request(env, previous):
    client(env, previous)
    repo = env.repo
    repo.git("config", "user.name", "Original Fix Starter")
    repo.git("config", "user.email", "starter@example.test")
    started = repo.forge("fix", "start", "Show a greeting", "--done", "Readers see a greeting")
    assert started.returncode == 0, started.stdout + started.stderr
    where = worktree(repo, "fix/show-a-greeting")
    repo.git("config", "user.name", "Later Contributor")
    repo.git("config", "user.email", "contributor@example.test")
    env.commit(where, "greeting.txt", "Welcome\n", "Write the greeting")

    shown = rows(board(repo))["show-a-greeting"]
    assert shown["pr"]["number"] is None and shown["pr"]["url"] is None
    assert (shown["started_by"], shown["started_by_login"]) == ("Original Fix Starter", None)


@pytest.mark.parametrize("evidence", ["local", "published", "summary"])
def test_8_approval_identity_comes_from_the_approvers_own_record(
        env, monkeypatch, unsynced_up, evidence):
    if evidence == "local":
        client(env, False)
        repo = env.repo
        owner_doc = STORY_DOC + "\n## For the builders\n\nOwner: plan-owner\n"
        repo.git("config", "user.name", "Actual Approver")
        repo.git("config", "user.email", "approver@example.test")
        approve_story(repo, owner_doc)
        waiting = repo.forge("story", "new", "WAIT", "Waiting for an approver")
        assert waiting.returncode == 0, waiting.stdout + waiting.stderr
        env.commit(worktree(repo, "story/WAIT"), "plans/WAIT.md", owner_doc, "Name the plan owner")
        unapproved = rows(board(repo))["WAIT"]
        assert (unapproved["approved_by"], unapproved["approved_by_login"]) == (None, None)
        approved = rows(board(repo))["SHOP"]
        assert (approved["approved_by"], approved["approved_by_login"]) == ("Actual Approver", None)
        return

    history = History(unsynced_up, monkeypatch)
    history.story()
    history.item("approved-part", 21, 10, task="T1", long_history=evidence == "summary")
    history.publish()
    upgraded = unsynced_up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    # A PR's shared time record is GitHub evidence, including an explicit actor
    # login when present. It belongs to this approver, never the plan owner.
    if evidence in ("published", "summary"):
        record = history.record(21)
        approval = next(event for event in record["events"] if event["event"] == "plan approved")
        if evidence == "published":
            approval["by_login"] = "actual-approver"
        else:
            # GitHub can hold the actor in its compacted record rather than an event.
            record["summary"]["approved_by"] = approval["by"]
            record["events"].remove(approval)
        merged = history.stored()[21]
        body = merged["body"]
        beginning = body.index("<!-- forge:time-record ") + len("<!-- forge:time-record ")
        end = body.index(" -->", beginning)
        merged["body"] = body[:beginning] + json.dumps(record) + body[end:]
        history.prs = list(history.stored().values())
        history.prs = [merged if one["number"] == 21 else one for one in history.prs]
        history.publish()
        monkeypatch.setenv("FORGE_NOW", (NOW + timedelta(seconds=121)).isoformat())
    shown = rows(board(history.repo))["SHOP/T1"]
    assert (shown["approved_by"], shown["approved_by_login"]) == (
        "Plan Approver", "actual-approver" if evidence == "published" else None)


def _remove_gh(env, monkeypatch):
    # Real Git and platform probes remain available; no directory can supply gh.
    isolated = env.tmp / "without-gh"
    isolated.mkdir()
    for command in ("git", "sysctl", "vm_stat"):
        executable = shutil.which(command)
        if executable:
            _install(isolated, command, f"#!{sys.executable}\nimport subprocess, sys\n"
                     f"sys.exit(subprocess.run([{executable!r}, *sys.argv[1:]]).returncode)\n")
    monkeypatch.setenv("PATH", isolated.as_posix())
    assert shutil.which("gh") is None


@pytest.mark.parametrize("case", ["gh-absent", "github-unreachable", "adopted-upgrade"])
def test_1_board_people_keep_loaded_names_and_logins(env, monkeypatch, unsynced_up, case):
    if case == "adopted-upgrade":
        history = History(unsynced_up, monkeypatch)
        history.story()
        plan = (history.repo.path / "plans/SHOP.md").read_text("utf-8")
        history.commit(history.repo.path, "plans/SHOP.md",
                       plan + "\n## For the builders\n\nOwner: plan-owner\n",
                       "Assign the plan owner", NOW - timedelta(days=20))
        history.repo.git("merge", "-q", "--ff-only", "main", cwd=worktree(history.repo, "story/SHOP"))
        history.repo.git("push", "-q", "origin", "story/SHOP")
        history.item("recorded-people", 21, 10)
        history.publish()
        upgraded = unsynced_up.run(RELEASE)
        assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
        env, repo, item = history.env, history.repo, "recorded-people"
        now, author, merger = NOW, "Original Starter", "Human Merger"
        author_login, merger_login = "starter", "merger"
    else:
        client(env, False)
        repo = env.repo
        now = datetime.now(timezone.utc)
        monkeypatch.setenv("FORGE_NOW", now.isoformat())
        repo.git("config", "user.name", "Git Builder")
        repo.git("config", "user.email", "builder@example.test")
        item, _ = env.start_fix()
        repo.git("merge", "-q", "--no-edit", "fix/tidy-readme")
        repo.git("push", "-q", "origin", "main")
        author, author_login = "Git Builder", "builder-dev"
        merger = merger_login = "merge-owner"
        merged = pr(21, "fix/tidy-readme", {"name": author, "login": author_login}, now)
        merged["mergedBy"] = {"login": merger_login}
        older = pr(22, "manual-change", {"name": "Previous Builder", "login": author_login},
                   now - timedelta(days=7))
        github(env, [merged, older])
    env.gh.respond("api", "user", stdout="viewer-dev\n")
    before = len(env.gh.calls())
    warm_board = board(repo)  # Populate the real command's last-known records.
    warm = rows(warm_board)[item]
    assert warm["started_by_login"] == author_login
    assert warm["merged_by"]["login"] == merger_login
    if case != "adopted-upgrade":
        [trend_person] = [person for person in warm_board["team"]["trends"]["people"]
                          if person["login"] == author_login]
        assert trend_person["name"] == warm["started_by"] == author

    if case == "github-unreachable":
        env.gh.respond("pr", "list", exit=1, stderr="GitHub is unreachable\n")
        env.gh.respond("api", exit=1, stderr="GitHub is unreachable\n")
    else:
        _remove_gh(env, monkeypatch)

    for seconds in (0, 121):
        monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=seconds)).isoformat())
        shown = board(repo)
        person = rows(shown)[item]
        assert (person["started_by"], person["started_by_login"]) == (author, author_login)
        assert person["merged_by"] == {"name": merger, "login": merger_login}
        assert shown["viewer"] == "viewer-dev"
        if case == "adopted-upgrade":
            plan_owner = rows(shown)["SHOP"]
            assert (plan_owner["developer"], plan_owner["developer_login"]) == ("plan-owner", "plan-owner")
    assert not [call for call in env.gh.calls()[before:] if call[:1] == ["api"] and (
        any("object(oid:" in arg for arg in call)
        or any(arg.startswith("repos/{owner}/{repo}/commits/") and "/check-runs" not in arg
               for arg in call))]
