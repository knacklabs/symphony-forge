"""Real board reads retain names and add known logins, including older clients.

Audit: missing login fields and name-based guesses fail at the real command.
Existing board coverage only asserts names. Only GitHub is faked; no seam is added.
"""
from datetime import datetime, timedelta, timezone
import json

import pytest

from test_board_counts import board, github, rows
from test_board_trends import pr
from test_board_after_upgrade import History
from test_close import STORY_DOC, approve_story, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FORGE-BOARD-3"


def _github_actors(env, logins):
    # GitHub resolves only commits in the query, from its independent actor data.
    (env.repo.bin / "actor-logins.json").write_text(json.dumps(logins), "utf-8")
    path = env.repo.bin / "gh"
    source = path.read_text("utf-8")
    source = source.replace('responses = here / "gh-responses.json"', '''if args[:1] == ["api"] and len(args) > 1 and args[1].startswith("repos/{owner}/{repo}/commits/"):
    logins = json.loads((here / "actor-logins.json").read_text("utf-8"))
    login = logins.get(args[1].rsplit("/", 1)[1])
    print(json.dumps({"author": {"login": login} if login else None}))
    sys.exit(0)
if args[:2] == ["api", "graphql"] and any("object(oid:" in arg for arg in args):
    import re
    logins = json.loads((here / "actor-logins.json").read_text("utf-8"))
    query = next(arg for arg in args if "object(oid:" in arg)
    actors = {alias: {"author": {"user": {"login": logins[sha]} if logins.get(sha) else None}}
              for alias, sha in re.findall(r'(\\w+):object\\(oid:"([0-9a-f]{40})"\\)', query)}
    print(json.dumps({"data": {"repository": actors}}))
    sys.exit(0)
responses = here / "gh-responses.json"''')
    path.write_text(source, "utf-8")


def _team_actor_reads(env, monkeypatch):
    client(env, False)
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    logins, names = {}, {}
    for index in range(12):
        item = f"actor-{index}"
        name, login = f"Builder {index}", f"builder-{index}"
        env.repo.git("config", "user.name", name)
        env.repo.git("config", "user.email", f"builder-{index}@example.test")
        started = env.repo.forge("fix", "start", "Keep names", "--done", "Names stay", "--slug", item)
        assert started.returncode == 0, started.stdout + started.stderr
        logins[env.repo.git("rev-parse", f"fix/{item}")] = login
        names[item] = (name, login)
    _github_actors(env, logins)
    before = len(env.gh.calls())
    for seconds in (0, 121):
        monkeypatch.setenv("FORGE_NOW", (now + timedelta(seconds=seconds)).isoformat())
        visible = rows(board(env.repo))
        assert {item: (visible[item]["started_by"], visible[item]["started_by_login"])
                for item in names} == names
    calls = env.gh.calls()[before:]
    actor_calls = [call for call in calls if call[:1] == ["api"] and (
        call[1:2] == ["graphql"] and any("object(oid:" in arg for arg in call)
        or len(call) > 1 and call[1].startswith("repos/{owner}/{repo}/commits/"))]
    assert len(actor_calls) == 1, "Known commit identities must be batched and retained beyond a minute"


def _compacted_past_work(unsynced_up, monkeypatch):
    # Create actual earlier-release work before upgrading. The shared history
    # publisher, rather than this test, must produce the compacted actor summary.
    history = History(unsynced_up, monkeypatch)
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "42+approver-dev@users.noreply.github.com")
    history.story()
    monkeypatch.setenv("GIT_AUTHOR_EMAIL", "43+starter-dev@users.noreply.github.com")
    history.item("long-history", 21, 10, task="T1", long_history=True)
    monkeypatch.delenv("GIT_AUTHOR_EMAIL")
    history.publish()
    upgraded = unsynced_up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert history.record(21)["summary"], "Real publication must compact the earlier rounds"
    assert not history.repo.git("branch", "--list", "task/SHOP-T1")
    part = rows(board(history.repo))["SHOP/T1"]
    assert (part["started_by"], part["started_by_login"]) == ("Original Starter", "starter-dev")
    assert (part["approved_by"], part["approved_by_login"]) == ("Plan Approver", "approver-dev")
    # Another laptop has no retained actor cache or local events to conceal lost identity.
    clone = unsynced_up.tmp / "past-work-viewer"
    history.repo.git("clone", "-q", history.remote, clone.as_posix())
    history.repo.path = clone
    shared = rows(board(history.repo))["SHOP/T1"]
    assert (shared["started_by"], shared["started_by_login"]) == ("Original Starter", "starter-dev")
    assert (shared["approved_by"], shared["approved_by_login"]) == ("Plan Approver", "approver-dev")


@pytest.mark.parametrize("previous", [False, True, "compacted", "team"],
                         ids=["new-client", "earlier-adoption", "compacted-past-work", "team-actors"])
def test_1_board_people_keep_names_and_known_github_logins(env, monkeypatch, previous, unsynced_up):
    if previous == "team":
        _team_actor_reads(env, monkeypatch)
        return
    if previous == "compacted":
        _compacted_past_work(unsynced_up, monkeypatch)
        return
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
    _github_actors(env, {head: "builder-dev"})
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
