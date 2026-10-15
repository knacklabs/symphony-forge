"""Real board reads retain names and add known logins, including older clients.

Audit: recorded logins survive; git names and emails never imply a login.
Existing board coverage only asserts names. Only GitHub is faked; no seam is added.
"""
from datetime import datetime, timedelta, timezone
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

STORY = "FORGE-BOARD-3"


def _without_github_cli(env, monkeypatch, previous):
    # Keep real Git available while removing every directory that could supply gh.
    # An uninstalled CLI differs from the existing unreachable-service cases.
    client(env, previous)
    env.repo.git("config", "user.name", "Local Builder")
    env.repo.git("config", "user.email", "local-dev@users.noreply.github.com")
    started = env.repo.forge("fix", "start", "Keep local work", "--done", "Local work shows", "--slug", "local-work")
    assert started.returncode == 0, started.stdout + started.stderr
    env.repo.git("config", "user.name", "Plain Git Author")
    env.repo.git("config", "user.email", "plain@example.test")
    started = env.repo.forge("fix", "start", "Keep plain authors", "--done", "Names stay", "--slug", "plain-author")
    assert started.returncode == 0, started.stdout + started.stderr
    now = datetime.now(timezone.utc)
    last_week = now - timedelta(days=now.weekday() + 7)
    github(env, [pr(31, "manual-change", {"name": "Cached Author", "login": "cached-dev"}, last_week)])
    assert rows(board(env.repo))["plain-author"]["started_by_login"] is None
    isolated = env.tmp / "without-gh"
    isolated.mkdir()
    for command in ("git", "sysctl", "vm_stat"):
        executable = shutil.which(command)
        if executable:
            _install(isolated, command, f"#!{sys.executable}\nimport subprocess, sys\n"
                     f"sys.exit(subprocess.run([{executable!r}, *sys.argv[1:]]).returncode)\n")
    monkeypatch.setenv("PATH", isolated.as_posix())
    assert shutil.which("gh") is None
    data = board(env.repo)
    assert data["viewer"] is None
    item = rows(data)["local-work"]
    # The narrowed contract keeps names with null logins for every author kind offline.
    assert (item["started_by"], item["started_by_login"]) == ("Local Builder", None)
    plain = rows(data)["plain-author"]
    assert (plain["started_by"], plain["started_by_login"]) == ("Plain Git Author", None)
    people = data["team"]["trends"]["people"]
    assert any(person["name"] == "Cached Author" for person in people)
    assert all(person["login"] is None for person in people)
    assert all(pr["author_login"] is None for pr in data["team"]["around_forge"])
    assert item["stage"] == "started" and item["intervals"]
    out = env.tmp / "offline.html"
    rendered = env.repo.forge("board", "--out", out.as_posix())
    assert rendered.returncode == 0, rendered.stdout + rendered.stderr
    assert "Keep local work" in out.read_text("utf-8")
    assert "Keep plain authors" in out.read_text("utf-8")


def _team_actor_reads(env, monkeypatch):
    client(env, False)
    now = datetime.now(timezone.utc)
    monkeypatch.setenv("FORGE_NOW", now.isoformat())
    names = {}
    for index in range(12):
        item = f"actor-{index}"
        name = f"Builder {index}"
        env.repo.git("config", "user.name", name)
        email = (f"builder-{index}@example.test" if index % 2 == 0
                 else f"{index}+builder-{index}@users.noreply.github.com")
        env.repo.git("config", "user.email", email)
        started = env.repo.forge("fix", "start", "Keep names", "--done", "Names stay", "--slug", item)
        assert started.returncode == 0, started.stdout + started.stderr
        names[item] = (name, None)
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
    assert actor_calls == [], "Git names and emails must cause no GitHub identity requests"


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
    assert (part["started_by"], part["started_by_login"]) == ("Original Starter", "starter")
    assert (part["approved_by"], part["approved_by_login"]) == ("Plan Approver", None)
    # The owner narrowed identity to records that hold a login: PR author survives
    # compaction, but approval names and noreply emails supply no login.
    # Another laptop has no local events to conceal lost identity.
    clone = unsynced_up.tmp / "past-work-viewer"
    history.repo.git("clone", "-q", history.remote, clone.as_posix())
    history.repo.path = clone
    shared = rows(board(history.repo))["SHOP/T1"]
    assert (shared["started_by"], shared["started_by_login"]) == ("Original Starter", "starter")
    assert (shared["approved_by"], shared["approved_by_login"]) == ("Plan Approver", None)


def _older_pull_request_history(unsynced_up, monkeypatch):
    # Older completed work must retain its recorded PR people after it leaves
    # the JSON board's recent window, with no surviving branch or local events.
    history = History(unsynced_up, monkeypatch)
    history.item("older-history", 21, 10, long_history=True)
    history.publish()
    upgraded = unsynced_up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    assert history.record(21)["summary"], "The upgrade must compact the actual old review history"
    assert not history.repo.git("branch", "--list", "fix/older-history")
    history.at(NOW + timedelta(weeks=10))
    assert "older-history" not in rows(board(history.repo))
    before = len(history.env.gh.calls())
    for read in range(2):
        out = unsynced_up.tmp / f"older-history-{read}.html"
        rendered = history.repo.forge("board", "--out", out.as_posix())
        assert rendered.returncode == 0, rendered.stdout + rendered.stderr
        page = out.read_text("utf-8")
        assert "Readers see older-history" in page
        assert "Started by Original Starter." in page
        assert "Human Merger" in page
    calls = history.env.gh.calls()[before:]
    older_lists = [call for call in calls if call[:2] == ["pr", "list"]
                   and "--search" in call
                   and call[call.index("--search") + 1].startswith("merged:*..")]
    assert len(older_lists) == 1, "Full history shares one cached bulk lookup for older PR people"


@pytest.mark.parametrize("previous", [False, True, "compacted", "older-pr-history", "team", "offline-new", "offline-adopted"],
                         ids=["new-client", "earlier-adoption", "compacted-past-work", "older-pr-history",
                              "team-actors", "offline-new", "offline-adopted"])
def test_1_board_people_keep_names_and_known_github_logins(env, monkeypatch, previous, unsynced_up):
    if previous in ("offline-new", "offline-adopted"):
        _without_github_cli(env, monkeypatch, previous == "offline-adopted")
        return
    if previous == "team":
        _team_actor_reads(env, monkeypatch)
        return
    if previous == "compacted":
        _compacted_past_work(unsynced_up, monkeypatch)
        return
    if previous == "older-pr-history":
        _older_pull_request_history(unsynced_up, monkeypatch)
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
    assert (part["approved_by"], part["approved_by_login"]) == ("Plan Owner", None)
    assert (part["developer"], part["developer_login"]) == ("viewer-dev", "viewer-dev")
    assert part["merged_by"] == {"name": "Merge Owner", "login": "merge-owner"}
    assert visible["SHOP"]["approved_by_login"] is None
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
