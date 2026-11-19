"""Promoted and previously published task histories keep their first start and work.

Audit: the earlier synthetic task fixture could not catch a broken promotion.
Real fix work, promotion and publication must keep the original start and activity
on a second machine. The installed-release test owns old published-start repair.
Only worker, review and GitHub edges are faked; no production seam is added.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone

import conftest
from test_board_after_upgrade import NOW
from test_close import CLEAN, GREEN, body, env  # noqa: F401
from test_item_time_history import row
from test_pull_request_body_limit import publish_snapshot
from test_story import READER, approved_constitution, worktree
from test_worker import install_claude

STORY = "FIX-EXACT-WAIT-TIMES"


def prepare_rewritten_published_task(history):
    repo = history.repo
    item, branch = "SHOP/T1", "task/SHOP-T1"
    path = ".factory/stories/SHOP/tasks/T1.json"
    where = history.up.tmp / "rewritten-task"
    repo.git("worktree", "add", "-q", "-b", branch, where.as_posix(), "main")

    started_at = NOW - timedelta(days=5, seconds=17)
    rewritten_at = NOW - timedelta(days=1)
    state = {"kind": "task", "branch": branch, "status": "working",
             "why": "Readers see a saved basket", "done_when": "The basket stays saved",
             "base": repo.git("rev-parse", "main"),
             "steps": [{"step": "start", "at": started_at.isoformat()}]}
    # The old release published the rewritten commit time as the start.
    history.commit(where, path, json.dumps(state), "Start the task", rewritten_at)
    history.commit(where, "basket.py", "SAVED = True\n", "Keep the basket", rewritten_at)
    head = repo.git("rev-parse", "HEAD", cwd=where)
    repo.git("push", "-q", "origin", branch)
    repo.git("push", "-q", "origin", f"{head}:refs/pull/18/head")
    categories = ("building", "own_tests", "reviewing", "fixing_findings", "waiting_for_ci",
                  "waiting_in_line", "waiting_for_owner", "nothing_running")
    unknown_seconds = (NOW - rewritten_at).total_seconds()
    old_record = {"events": [{"id": "old-start", "item": item, "event": "item started",
                              "at": rewritten_at.isoformat()}],
                  "timings": [],
                  "state": {**state, "steps": [{"step": "start", "at": rewritten_at.isoformat()}]},
                  "clean_reviews": [], "rebuilt": True,
                  "summary": {"round": 1, "until": NOW.isoformat(),
                              "time_breakdown": dict.fromkeys(categories),
                              "working_seconds": 0, "waiting_seconds": 0,
                              "unknown_seconds": unknown_seconds, "total_seconds": unknown_seconds,
                              "rounds": [], "intervals": [], "seen": [], "known": False,
                              "folded": {"start": rewritten_at.isoformat(), "end": NOW.isoformat(),
                                         "working": 0, "waiting": 0, "unknown": unknown_seconds}}}
    published = ("Owner notes remain.\n<!-- forge:begin -->\n## How it went\n\n"
                 f"Started: {rewritten_at.isoformat()}\n"
                 "<!-- forge:time-record " + json.dumps(old_record, separators=(",", ":"))
                 + " -->\n<!-- forge:end -->\n")
    history.prs.append({"number": 18, "headRefName": branch, "headRefOid": head,
                        "baseRefName": "main", "state": "OPEN", "isDraft": False,
                        "title": "Keep the basket", "body": published, "mergedAt": None,
                        "mergedBy": None, "author": {"login": "starter", "name": "Starter"},
                        "url": "https://github.com/acme/shop/pull/18"})
    history.publish()
    return item, started_at


def assert_rewritten_published_task_start(history, item, started_at):
    repo = history.repo
    published_body = history.stored()[18]["body"]
    assert "Owner notes remain." in published_body
    assert f"Started: {started_at.isoformat()}" in published_body
    assert history.record(18)["state"]["steps"][0]["at"] == started_at.isoformat()

    clone_path = history.up.tmp / "published-history"
    repo.git("clone", "-q", history.remote, str(clone_path))
    fresh = conftest.Repo(clone_path, repo.bin)
    current = row(fresh, item)
    assert current["total_seconds"] == (NOW - started_at).total_seconds()
    assert current["folded_seconds"]["start"] == started_at.isoformat()


def test_4_fix_activity_survives_real_promotion_and_task_publication(env, monkeypatch):
    repo = env.repo
    began = datetime(2026, 11, 18, tzinfo=timezone.utc)
    at = lambda seconds: (began + timedelta(seconds=seconds)).isoformat()
    monkeypatch.setenv("FORGE_NOW", at(0))
    approved_constitution(repo)
    repo.write("plans/roadmap.json", json.dumps({"items": [{"key": "BASKET"}]}))
    repo.git("add", "plans/roadmap.json")
    repo.git("commit", "-q", "-m", "Add the basket story")
    repo.git("push", "-q", "origin", "main")
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))

    started = repo.forge("fix", "start", "Keep the basket saved", "--done",
                         "The basket stays saved", "--slug", "keep-baskets")
    assert started.returncode == 0, started.stdout + started.stderr
    where = worktree(repo, "fix/keep-baskets")
    (where / "basket.py").write_text("SAVED = True\n", "utf-8")
    install_claude(repo)
    clock = repo.bin / "wall-clock"
    clock.write_text(at(60), "utf-8")
    shim = repo.bin / "forge"
    original = shim.read_text("utf-8")
    shim.write_text(original.replace("from forge.cli import main",
        "from forge import repo\nfrom pathlib import Path\n"
        f"repo.now = lambda: Path({json.dumps(clock.as_posix())}).read_text('utf-8')\n"
        "from forge.cli import main"), "utf-8")
    sdk = repo.bin / "claude_agent_sdk" / "__init__.py"
    sdk.write_text(sdk.read_text("utf-8").replace(
        'yield SystemMessage("init",',
        f"Path({json.dumps(clock.as_posix())}).write_text({json.dumps(at(120))}, 'utf-8')\n"
        '    yield SystemMessage("init",'), "utf-8")
    try:
        with monkeypatch.context() as worker_env:
            worker_env.setenv("STUB_CLAUDE_COMMIT_FROM", "1")
            worked = repo.forge("work", "keep-baskets")
    finally:
        shim.write_text(original, "utf-8")
    assert worked.returncode == 0, worked.stdout + worked.stderr

    clock.write_text(at(180), "utf-8")
    env.reviews(CLEAN)
    env.checks(GREEN)
    closed = repo.forge("close", "keep-baskets")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    fix_pr_body = body(env.gh_calls("pr", "edit")[-1])
    env.open_pr(fix_pr_body)

    promoted = repo.forge("story", "new", "BASKET", "Keep baskets saved",
                          "--from-fix", "keep-baskets")
    assert promoted.returncode == 0, promoted.stdout + promoted.stderr
    clock.write_text(at(240), "utf-8")
    local = row(repo, "BASKET/SPEC")
    assert local["intervals"][0]["start"] == at(0)
    assert local["time_breakdown"]["building"] >= 60

    # Approve the generated story through Forge before its promoted task closes.
    plan = """# Baskets stay saved

## What changes for you

People can return to a saved basket.

## Why

People lose baskets when they leave.

## Done when

1. A saved basket is still there after signing out and back in.

## Tasks

| ID | Name | What it delivers | Covers | Scope | Tests | After | User-facing |
|---|---|---|---|---|---|---|---|
| SPEC | Keep baskets saved | Baskets stay saved | 1 | `basket.py` | `tests/test_first_start_survives_history_changes.py` | none | no |

New moving parts: none

## Risks

Risks: none

## Notes
"""
    story_branch = worktree(repo, "story/BASKET")
    (story_branch / "plans/BASKET.md").write_text(plan, "utf-8")
    repo.git("add", "plans/BASKET.md", cwd=story_branch)
    repo.git("commit", "-q", "-m", "Write the basket plan", cwd=story_branch)
    conftest._install(repo.bin, "claude", READER.format(python=sys.executable))
    read = repo.forge("read", "BASKET")
    assert read.returncode == 0, read.stdout + read.stderr
    approval = conftest._payload("PostToolUse", repo.path, "ExitPlanMode", {"plan": plan},
                                 {"plan": plan, "isAgent": False, "filePath": "/plans/plan.md"})
    approved = repo.forge("hook", "approval", input=json.dumps(approval))
    assert approved.returncode == 0, approved.stdout + approved.stderr
    repo.git("merge", "-q", "--ff-only", "story/BASKET")
    repo.git("push", "-q", "origin", "main")
    repo.git("fetch", "-q", "origin", "main", cwd=where)
    repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    repo.git("push", "-q", "origin", "task/BASKET-SPEC", cwd=where)
    clock.write_text(at(300), "utf-8")
    # The new task has no pull request yet. Its old fix's PR remains available.
    env.gh.respond("pr", "list", "--head", "task/BASKET-SPEC", stdout="[]")
    # Another machine publishes the task without the original fix's local logs.
    publisher = env.tmp / "task-publisher"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(publisher))
    env.repo.path = publisher
    task_closed = env.close("BASKET/SPEC")
    assert task_closed.returncode == 0, task_closed.stdout + task_closed.stderr
    task_pr_body = body(env.gh_calls("pr", "edit")[-1])
    assert f"Started: {at(0)}" in task_pr_body
    publish_snapshot(env, "BASKET/SPEC", task_pr_body)

    clone_path = env.tmp / "promoted-task-clone"
    repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(clone_path))
    fresh = conftest.Repo(clone_path, repo.bin)
    assert row(fresh, "BASKET/SPEC")["time_breakdown"]["building"] >= 60
