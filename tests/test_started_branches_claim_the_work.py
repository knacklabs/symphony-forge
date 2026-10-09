"""STORY: start-is-claim. Real commands and real git prove team claims.

Existing starts exercised local worktrees only; these guard remote publication,
failed publication, admission from another clone and durable author attribution.
The only external stand-in is a bare GitHub-edge remote (test-audit gate).
"""
import json
import shutil

import pytest

from conftest import ROOT, Repo
from test_board import seen
from test_setup import _fresh_client
from test_story import DOC, claude_plan, hook, ready, setup, worktree

STORY = "start-is-claim"


@pytest.fixture(params=[False, True], ids=["new-client", "adopted-v1.2.2"])
def client(repo, gh, tmp_path, request):
    if request.param:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-qc", "fix/adoption")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "fix/adoption")
    else:
        path, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = path
    # Configuration/release setup models history already landed before these starts.
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks"))
    repo.git("switch", "-qc", "fix/upgrade-client")
    setup(repo, kind="client")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks-after-sync"))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Upgrade the client")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/upgrade-client")
    repo.git("config", "core.hooksPath", str(tmp_path / "historical-hooks-after-sync"))
    repo.git("push", "-q", "origin", "main")
    repo.git("config", "--unset", "core.hooksPath")
    installed = repo.forge("sync")
    assert installed.returncode == 0, installed.stdout + installed.stderr
    assert repo.git("status", "--porcelain") == ""
    gh.respond("pr", "list", stdout="[]")
    return repo


def _approve(repo, claude_payload):
    path = ready(repo, "SHOP")
    repo.git("config", "user.name", "Plan Approver")
    approved = hook(repo, claude_plan(claude_payload, DOC, cwd=path))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    return path


def _start(repo, kind):
    if kind == "story":
        return repo.forge("story", "new", "SHOP", "Shoppers can save a basket"), "story/SHOP"
    if kind == "task":
        return repo.forge("task", "start", "SHOP/SAVE"), "task/SHOP-SAVE"
    return repo.forge("fix", "start", "Readers see a greeting", "--done", "The greeting is visible",
                      "--slug", "greeting"), "fix/greeting"


@pytest.mark.parametrize("kind", ["story", "task", "fix"])
def test_start_publishes_the_start_commit_as_the_claim(client, claude_payload, kind):
    if kind == "task":
        _approve(client, claude_payload)
    client.git("config", "user.name", "First Starter")
    started, branch = _start(client, kind)
    assert started.returncode == 0, started.stdout + started.stderr
    remote = client.git("ls-remote", "origin", f"refs/heads/{branch}")
    assert remote, f"{branch} was left local after start: {started.stdout} {started.stderr}"
    assert remote.split()[0] == client.git("rev-parse", branch)
    assert client.git("show", "-s", "--format=%an", branch) == "First Starter"


@pytest.mark.parametrize("kind", ["story", "task", "fix"])
def test_push_failure_says_the_work_stays_local(client, claude_payload, kind):
    if kind == "task":
        _approve(client, claude_payload)
    remote = client.path.parent / ("remote.git" if client.path.name == "repo" else "client.git")
    reject = remote / "hooks" / "pre-receive"
    reject.write_text('#!/bin/sh\necho "GitHub is refusing new branches" >&2\nexit 1\n', "utf-8")
    reject.chmod(0o755)
    started, branch = _start(client, kind)
    assert started.returncode == 0, started.stdout + started.stderr
    assert f"Could not push {branch} to GitHub; the work stays local." in started.stderr
    assert "GitHub is refusing new branches" in started.stderr
    assert client.git("branch", "--list", branch)
    assert client.git("status", "--porcelain", cwd=worktree(client, branch)) == ""
    assert client.git("ls-remote", "origin", f"refs/heads/{branch}") == ""


def test_second_checkout_is_refused_with_the_first_starters_name(client, claude_payload, tmp_path):
    plan = _approve(client, claude_payload)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    teammate = tmp_path / "teammate"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(teammate))
    second = Repo(teammate, client.bin)
    second.git("config", "user.name", "Second Starter")
    client.git("config", "user.name", "First Starter")
    first, branch = _start(client, "task")
    assert first.returncode == 0, first.stdout + first.stderr
    refused = second.forge("task", "start", "SHOP/SAVE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "SHOP/SAVE is already started on task/SHOP-SAVE by First Starter." in refused.stderr
    assert "Next: forge work SHOP/SAVE" in refused.stderr
    assert second.git("branch", "--list", branch) == ""


def test_board_shows_start_commit_authors_beside_the_plan_approver(client, claude_payload, tmp_path):
    # A teammate already has this checkout when the others claim their work.
    observer = tmp_path / "observer"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(observer))
    viewer = Repo(observer, client.bin)
    client.git("config", "user.name", "Story Starter")
    plan = _approve(client, claude_payload)
    client.git("config", "user.name", "Part Starter")
    part, _ = _start(client, "task")
    assert part.returncode == 0, part.stdout + part.stderr
    client.git("config", "user.name", "Fix Starter")
    fixed, _ = _start(client, "fix")
    assert fixed.returncode == 0, fixed.stdout + fixed.stderr
    # Later contributors change the head, never the starter's identity.
    client.git("config", "user.name", "Later Contributor")
    (plan / "README.md").write_text("More story detail\n", "utf-8")
    client.git("add", "README.md", cwd=plan)
    client.git("commit", "-qam", "Explain the story", cwd=plan)
    client.git("push", "-q", "origin", "story/SHOP", cwd=plan)
    for branch, file in (("task/SHOP-SAVE", "basket.txt"), ("fix/greeting", "greeting.txt")):
        folder = worktree(client, branch)
        (folder / file).write_text("A later contribution\n", "utf-8")
        client.git("add", file, cwd=folder)
        client.git("commit", "-qm", "Contribute to the work", cwd=folder)
        client.git("push", "-q", "origin", branch, cwd=folder)
    listing = viewer.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    items = json.loads(listing.stdout)["items"]
    story = next(row for row in items if row["id"] == "SHOP")
    part = next(row for row in story["children"] if row["id"] == "SHOP/SAVE")
    fix = next(row for row in items if row["id"] == "greeting")
    assert story["started_by"] == "Story Starter"
    assert story["approved_by"] == "Plan Approver"
    assert part["started_by"] == "Part Starter"
    assert part["approved_by"] == "Plan Approver"
    assert fix["started_by"] == "Fix Starter"
    assert fix["approved_by"] is None
    page = viewer.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    words = seen(observer / ".git" / "forge" / "board.html")
    for phrase in ("Started by Story Starter. Approved by Plan Approver.",
                   "Started by Part Starter. Approved by Plan Approver.",
                   "Started by Fix Starter."):
        assert phrase in words, words
