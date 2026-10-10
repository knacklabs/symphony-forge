"""STORY: start-is-claim. Recovery preserves authors after rewritten Git history.

The existing cleanup proof retains start ancestry. These command lifecycles lose
it through replay or a copied plan, then ask a fresh teammate's board for authors.
Only remote review/check services and GitHub's squash API are faked; Git is real.
No production seam is needed (test-audit authoring gate).
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, ROOT, Repo, _install
from test_board import seen
from test_close import CLEAN, CODEX_STUB, GREEN, PIN, Forge
from test_started_branches_claim_the_work import client  # noqa: F401
from test_starter_names_survive_branch_cleanup import _github_squash, _start
from test_story import DOC, claude_plan, hook, worktree

STORY = "start-is-claim"


@pytest.fixture
def flow(client, gh, tmp_path, monkeypatch):
    # Historical client configuration, before any claims under test begin.
    client.git("config", "core.hooksPath", (tmp_path / "historical-narrow-hooks").as_posix())
    client.git("switch", "-qc", "fix/configure-client")
    config = client.path / "forge.toml"
    config.write_text(config.read_text("utf-8") +
                      'merge = "agent"\nchecks = ["tests", "forge-pr-check"]\n', "utf-8")
    roadmap = client.path / "plans/roadmap.json"
    roadmap.write_text(json.dumps({"items": [{"key": "SHOP"}, {"key": "CHECK"}]}), "utf-8")
    client.git("add", "-A")
    client.git("commit", "-qm", "Configure reviewed client merges")
    client.git("switch", "-q", "main")
    client.git("merge", "-q", "--ff-only", "fix/configure-client")
    client.git("push", "-q", "origin", "main")
    client.git("branch", "-D", "fix/configure-client", "fix/upgrade-client")
    if client.git("branch", "--list", "fix/adoption"):
        client.git("branch", "-D", "fix/adoption")
    client.git("config", "--unset", "core.hooksPath")
    skill = tmp_path / "autoreview"
    (skill / "scripts").mkdir(parents=True)
    shutil.copy(ROOT / "tests/stubs/autoreview", skill / "scripts/autoreview")
    (skill / ".upstream-sha").write_text(PIN + "\n", "utf-8")
    monkeypatch.setenv("AUTOREVIEW", str(skill / "scripts/autoreview"))
    monkeypatch.setenv("AUTOREVIEW_STUB", str(tmp_path / "reviews.json"))
    monkeypatch.setenv("FORGE_CHECKS_WAIT", "0")
    _install(client.bin, "codex", CODEX_STUB.format(python=sys.executable))
    result = Forge(client, gh, tmp_path)
    result.reviews(CLEAN)
    result.checks(GREEN)
    gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    gh.respond("pr", "edit")
    gh.respond("pr", "ready")
    return result


def _finish(client, gh, tmp_path, item, branch):
    closed = client.forge("close", item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = client.git("rev-parse", branch)
    _github_squash(client, branch, tmp_path)
    merged = client.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert client.git("branch", "--list", branch) == ""
    assert client.git("ls-remote", "origin", f"refs/heads/{branch}") == ""
    _install(client.bin, "gh", GH_STUB.format(python=sys.executable))
    gh.respond("pr", "list", stdout="[]")
    return head


def _observer(client, tmp_path):
    observer = tmp_path / "fresh-observer"
    client.git("clone", "-q", client.git("remote", "get-url", "origin"), str(observer))
    viewer = Repo(observer, client.bin)
    listing = viewer.forge("board", "--json")
    assert listing.returncode == 0, listing.stdout + listing.stderr
    page = viewer.forge("board")
    assert page.returncode == 0, page.stdout + page.stderr
    return json.loads(listing.stdout)["items"], seen(observer / ".git/forge/board.html")


def _plan(client, claude_payload, key, doc, rejected=False):
    client.git("config", "user.name", "Original Story Starter")
    client.git("config", "user.email", "story-starter@example.test")
    where = _start(client, f"story/{key}",
                   ("story", "new", key, "Shoppers can save a basket"), rejected)
    (where / "plans" / f"{key}.md").write_text(doc, "utf-8")
    read = client.forge("read", key)
    assert read.returncode == 0, read.stdout + read.stderr
    client.git("config", "user.name", "Plan Approver")
    client.git("config", "user.email", "plan-approver@example.test")
    approved = hook(client, claude_plan(claude_payload, doc, cwd=where))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    return where


def _remove_plan(client, key, where):
    client.git("worktree", "remove", str(where))
    client.git("branch", "-D", f"story/{key}")
    if client.git("ls-remote", "origin", f"refs/heads/story/{key}"):
        client.git("push", "-q", "origin", "--delete", f"story/{key}")
    client.git("fetch", "-q", "--prune", "origin")
    client.git("merge", "-q", "--ff-only", "origin/main")


def test_12_ownership_after_rejected_stacked_start_close_replay_and_cleanup(
        client, flow, gh, tmp_path):
    parent = _start(client, "fix/parent", ("fix", "start", "Repair the parent", "--done",
                    "Parent is repaired", "--slug", "parent"), False)
    flow.commit(parent, "parent.txt", "Parent repaired\n", "Repair the parent")
    client.git("config", "user.name", "Original Followup Starter")
    client.git("config", "user.email", "followup-starter@example.test")
    # This real start uses the parent's unmerged checkout; its publication is rejected.
    remote = client.git("remote", "get-url", "origin")
    reject = Path(remote) / "hooks/pre-receive"
    reject.write_text('#!/bin/sh\nexit 1\n', "utf-8")
    reject.chmod(0o755)
    try:
        started = client.forge("fix", "start", "Repair the follow-up", "--done",
                               "Follow-up is repaired", "--slug", "followup", cwd=parent)
        assert started.returncode == 0, started.stdout + started.stderr
        assert "Could not push fix/followup to GitHub; the work stays local." in started.stderr
    finally:
        reject.unlink(missing_ok=True)
    followup = worktree(client, "fix/followup")
    original_start = client.git("rev-parse", "fix/followup")
    assert client.git("ls-remote", "origin", "refs/tags/forge-start/fix/followup") == ""
    client.git("config", "user.name", "Later Contributor")
    client.git("config", "user.email", "later-contributor@example.test")
    flow.commit(followup, "followup.txt", "Follow-up repaired\n", "Repair the follow-up")
    _finish(client, gh, tmp_path, "parent", "fix/parent")
    replayed = _finish(client, gh, tmp_path, "followup", "fix/followup")
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", original_start, replayed],
                              cwd=client.path, capture_output=True, text=True, encoding="utf-8")
    assert ancestry.returncode == 1, ancestry.stdout + ancestry.stderr
    assert not followup.exists()
    rows, words = _observer(client, tmp_path)
    fix = next(row for row in rows if row["id"] == "followup")
    assert fix["started_by"] == "Original Followup Starter"
    assert "Started by Original Followup Starter." in words, words


def test_13_ownership_after_copied_plan_first_part_cleanup(
        client, flow, gh, tmp_path, claude_payload):
    doc = DOC.replace("2. The basket page says when it was saved.\n", "")
    doc = "\n".join(line for line in doc.splitlines() if not line.startswith("| SHOW |")) + "\n"
    prerequisite = _plan(client, claude_payload, "SHOP", doc)
    part = _start(client, "task/SHOP-SAVE", ("task", "start", "SHOP/SAVE"), False)
    flow.commit(part, "src/basket.py", "saved = True\n", "Save the basket")
    _finish(client, gh, tmp_path, "SHOP/SAVE", "task/SHOP-SAVE")
    _remove_plan(client, "SHOP", prerequisite)
    # A cross-story dependency puts the first part on main and copies the plan.
    copied = doc.replace("`src/basket.py`", "`src/checkout.py`")
    copied = copied.replace("| none | no |", "| SHOP/SAVE | no |")
    plan = _plan(client, claude_payload, "CHECK", copied, rejected=True)
    assert client.git("ls-remote", "origin", "refs/tags/forge-start/story/CHECK") == ""
    client.git("config", "user.name", "Original Part Starter")
    client.git("config", "user.email", "part-starter@example.test")
    part = _start(client, "task/CHECK-SAVE", ("task", "start", "CHECK/SAVE"), True)
    client.git("config", "user.name", "Later Contributor")
    client.git("config", "user.email", "later-contributor@example.test")
    flow.commit(part, "src/checkout.py", "checkout = True\n", "Save the checkout")
    _finish(client, gh, tmp_path, "CHECK/SAVE", "task/CHECK-SAVE")
    _remove_plan(client, "CHECK", plan)
    rows, words = _observer(client, tmp_path)
    story = next(row for row in rows if row["id"] == "CHECK")
    part = next(row for row in story["children"] if row["id"] == "CHECK/SAVE")
    assert story["started_by"] == "Original Story Starter"
    assert part["started_by"] == "Original Part Starter"
    assert story["approved_by"] == part["approved_by"] == "Plan Approver"
    for sentence in ("Started by Original Story Starter.", "Started by Original Part Starter.",
                     "Approved by Plan Approver."):
        assert sentence in words, words
