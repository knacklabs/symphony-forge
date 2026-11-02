"""A ready pull request can be continued, closed and merged from another checkout."""
from __future__ import annotations

import json
import sys

import pytest

from conftest import GH_STUB, Repo, _install
from test_close import STORY_DOC, body, env
from test_fix_drop import _github
from test_machine_views import github, pull
from test_next_local_progress import _client
from test_story import worktree

STORY = "FORGE-HANDOVER-1"


def _github_merge_edge(repo: Repo, remote: str, branch: str) -> None:
    source = GH_STUB.format(python=sys.executable)
    merge = '''if args[:2] == ["pr", "merge"]:
    checkout = here / ("github-merge-" + PULL_BRANCH.replace("/", "-"))
    subprocess.run(["git", "clone", "-q", REMOTE_PATH, str(checkout)], check=True)
    subprocess.run(["git", "fetch", "-q", "origin", PULL_BRANCH], cwd=checkout, check=True)
    actual = subprocess.run(["git", "rev-parse", "FETCH_HEAD"], cwd=checkout, check=True,
                            capture_output=True, text=True).stdout.strip()
    expected = args[args.index("--match-head-commit") + 1]
    if actual != expected:
        sys.exit(1)
    subprocess.run(["git", "merge", "--squash", "FETCH_HEAD"], cwd=checkout, check=True,
                   capture_output=True)
    subprocess.run(["git", "commit", "-q", "-m", args[args.index("--subject") + 1]],
                   cwd=checkout, check=True)
    subprocess.run(["git", "push", "-q", "origin", "main"], cwd=checkout, check=True)
    sys.exit(0)
'''.replace("REMOTE_PATH", repr(remote)).replace("PULL_BRANCH", repr(branch))
    source = source.replace('sys.stderr.write("stub gh: no response for: gh "', merge
                            + 'sys.stderr.write("stub gh: no response for: gh "')
    _install(repo.bin, "gh", source)


def _pr(env, branch: str, head: str, pr_body: str) -> None:
    pr = pull(7, branch)
    pr.update(headRefOid=head, title="Repair the page", url="https://github.com/acme/shop/pull/7",
              body=pr_body)
    github(env.gh, [pr])
    env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([pr]))
    env.gh.respond("pr", "view", branch, stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefName": branch,
        "headRefOid": head, "title": "Repair the page", "isDraft": False, "body": pr_body,
        "mergeable": "MERGEABLE"}))
    env.gh.respond("pr", "view", "7", "--json", "state", "--jq", ".state", stdout="MERGED")


def _clone(env, tmp_path, name: str) -> Repo:
    remote = env.repo.git("remote", "get-url", "origin")
    path = tmp_path / name
    env.repo.git("clone", "-q", remote, str(path))
    return Repo(path, env.repo.bin)


def test_3_merge_uses_shared_readiness_after_another_machine_closes_again(env, tmp_path):
    _client(env.repo, env.gh, tmp_path, False)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8") + 'merge = "agent"\n')
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    env.open_pr("")
    assert env.close(item).returncode == 0
    branch = f"fix/{item}"
    machine = _clone(env, tmp_path, "returning-machine")
    closed = machine.forge("close", item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    old_head = machine.git("rev-parse", branch)
    machine.git("worktree", "remove", str(worktree(machine, branch)))

    env.commit(where, "greeting.txt", "Hello from the other machine\n")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = env.repo.git("rev-parse", branch)
    assert head != old_head
    _pr(env, branch, head, body(env.gh_calls("pr", "edit")[-1]))
    _github_merge_edge(env.repo, env.repo.git("remote", "get-url", "origin"), branch)

    before = len(env.gh_calls("pr", "merge"))
    merged = machine.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    calls = env.gh_calls("pr", "merge")[before:]
    assert len(calls) == 1
    assert calls[0][calls[0].index("--match-head-commit") + 1] == head
    assert not any(line == f"branch refs/heads/{branch}" for line in
                   machine.git("worktree", "list", "--porcelain").splitlines())


@pytest.mark.parametrize("adopted,command", [(False, "work"), (False, "close"), (True, "work")],
                         ids=["new-work", "new-close", "earlier-adopted-work"])
def test_2_pickup_keeps_a_newly_dropped_fix_inactive(env, adopted, command, tmp_path):
    _client(env.repo, env.gh, tmp_path, adopted)
    item, _ = env.start_fix()
    branch = f"fix/{item}"
    env.repo.git("push", "-q", "origin", branch)
    machine = _clone(env, tmp_path, "stale-machine")
    stale = machine.git("rev-parse", f"origin/{branch}")
    _github(env.repo)
    dropped = env.repo.forge("fix", "drop", item, "--because", "The owner no longer needs this fix")
    assert dropped.returncode == 0, dropped.stdout + dropped.stderr
    assert machine.git("rev-parse", f"origin/{branch}") == stale

    refused = machine.forge(command, item)
    assert not any(line == f"branch refs/heads/{branch}" for line in
                   machine.git("worktree", "list", "--porcelain").splitlines())
    assert refused.returncode != 0
    assert refused.stderr == f"Fix {item} is dropped.\nNext: forge fix drop {item} --undo\n"
    assert machine.git("ls-remote", "origin", f"refs/heads/{branch}").split()[0] != stale


@pytest.mark.parametrize("adopted", [False, True], ids=["new repo", "earlier adopted"])
def test_1_a_ready_item_merges_from_a_machine_with_no_checkout(env, adopted, tmp_path):
    _client(env.repo, env.gh, tmp_path, adopted)
    config = env.repo.path / "forge.toml"
    env.commit(env.repo.path, "forge.toml", config.read_text("utf-8")
               + 'merge = "agent"\nworkers = "claude"\n')
    env.repo.git("push", "-q", "origin", "main")
    remote = env.repo.git("remote", "get-url", "origin")
    _github_merge_edge(env.repo, remote, "fix/tidy-readme")

    item, _ = env.start_fix()
    env.open_pr("")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    ready_body = body(env.gh_calls("pr", "edit")[-1])
    branch = f"fix/{item}"
    head = env.repo.git("rev-parse", branch)

    if not adopted:
        reused = _clone(env, tmp_path, "reused-machine")
        reused.git("fetch", "-q", "origin", branch)
        reused.git("switch", "-q", "--track", "-c", branch, f"origin/{branch}")
        reused.git("switch", "-q", "main")
        closed_here = reused.forge("close", item)
        assert closed_here.returncode == 0, closed_here.stdout + closed_here.stderr
        reused.git("fetch", "-q", "origin", branch)
        head = reused.git("rev-parse", f"origin/{branch}")
        ready_body = body(env.gh_calls("pr", "edit")[-1])

    checkout = _clone(env, tmp_path, "new-machine")
    checkout.git("fetch", "-q", "origin")
    assert not (checkout.path / ".git" / "forge" / "ready" / f"{item}.json").exists()
    _pr(env, branch, head, "" if adopted else ready_body)

    advice = checkout.forge("next")
    assert advice.returncode == 0, advice.stderr
    if not adopted:
        assert f"Next: forge merge {item}" in advice.stdout

    if adopted:
        missing = checkout.forge("merge", item)
        assert missing.returncode != 0
        assert missing.stderr == (f"Forge has no clean ready record for {item}.\n"
                                  f"Next: forge close {item}\n")
        checkout.git("worktree", "remove", str(worktree(checkout, branch)))
        closed_here = checkout.forge("close", item)
        assert closed_here.returncode == 0, closed_here.stdout + closed_here.stderr
        ready_body = body(env.gh_calls("pr", "edit")[-1])
        head = checkout.git("rev-parse", branch)
        _pr(env, branch, head, ready_body)

    before = len(env.gh_calls("pr", "merge"))
    merged = checkout.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    calls = env.gh_calls("pr", "merge")[before:]
    assert len(calls) == 1
    assert calls[0][calls[0].index("--match-head-commit") + 1] == head
    worktrees = checkout.git("worktree", "list", "--porcelain").split("\n")
    assert not any(line == f"branch refs/heads/{branch}" for line in worktrees)

    if not adopted:
        env.repo.git("fetch", "-q", "origin")
        env.repo.git("merge", "-q", "--ff-only", "origin/main")
        story_item, _ = env.start_approved_task(STORY_DOC)
        env.open_pr("")
        task_close = env.close(story_item)
        assert task_close.returncode == 0, task_close.stdout + task_close.stderr
        task_body = body(env.gh_calls("pr", "edit")[-1])
        task_branch = "task/SHOP-T1"
        task_head = env.repo.git("rev-parse", task_branch)
        _github_merge_edge(env.repo, remote, task_branch)
        task_machine = _clone(env, tmp_path, "task-machine")
        task_pr = pull(7, task_branch)
        task_pr.update(headRefOid=task_head, title="Save a basket",
                       url="https://github.com/acme/shop/pull/7", body=task_body)
        github(env.gh, [task_pr])
        env.gh.respond("pr", "list", "--state", "open", stdout=json.dumps([task_pr]))
        env.gh.respond("pr", "view", task_branch, stdout=json.dumps({
            "number": 7, "state": "OPEN", "baseRefName": "main", "headRefName": task_branch,
            "headRefOid": task_head, "title": "Save a basket", "isDraft": False,
            "body": task_body, "mergeable": "MERGEABLE"}))
        env.gh.respond("pr", "view", "7", "--json", "state", "--jq", ".state", stdout="MERGED")
        assert f"Next: forge merge {story_item}" in task_machine.forge("next").stdout
        before = len(env.gh_calls("pr", "merge"))
        task_merged = task_machine.forge("merge", story_item)
        assert task_merged.returncode == 0, task_merged.stdout + task_merged.stderr
        task_calls = env.gh_calls("pr", "merge")[before:]
        assert len(task_calls) == 1
        assert task_calls[0][task_calls[0].index("--match-head-commit") + 1] == task_head
        assert not any(line == f"branch refs/heads/{task_branch}" for line in
                       task_machine.git("worktree", "list", "--porcelain").splitlines())

        env.repo.git("fetch", "-q", "origin")
        env.repo.git("merge", "-q", "--ff-only", "origin/main")
        unfinished, where = env.start("unfinished", "fix/unfinished",
                                      ".factory/fixes/unfinished.json",
                                      {"kind": "fix", "why": "Repair the page",
                                       "done_when": "The page works"},
                                      {"page.py": "print('unfinished')\n"})
        env.repo.git("push", "-q", "--set-upstream", "origin", "fix/unfinished", cwd=where)
        unfinished_head = env.repo.git("rev-parse", "fix/unfinished")
        unfinished_machine = _clone(env, tmp_path, "unfinished-machine")
        _pr(env, "fix/unfinished", unfinished_head, "")
        next_work = unfinished_machine.forge("next")
        assert next_work.returncode == 0, next_work.stderr
        assert f"Next: forge work {unfinished}" in next_work.stdout
        resumed = unfinished_machine.forge("work", unfinished)
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
        assert any(line == "branch refs/heads/fix/unfinished" for line in
                   unfinished_machine.git("worktree", "list", "--porcelain").splitlines())

        diverged, diverged_where = env.start("diverged", "fix/diverged",
                                             ".factory/fixes/diverged.json",
                                             {"kind": "fix", "why": "Repair another page",
                                              "done_when": "The page works"},
                                             {"page.py": "print('started')\n"})
        env.open_pr("")
        diverged_close = env.close(diverged)
        assert diverged_close.returncode == 0, diverged_close.stdout + diverged_close.stderr
        branch = "fix/diverged"
        divergent_head = env.repo.git("rev-parse", branch)
        divergent_machine = _clone(env, tmp_path, "diverged-machine")
        divergent_machine.git("fetch", "-q", "origin", branch)
        divergent_machine.git("switch", "-q", "--track", "-c", branch, f"origin/{branch}")
        env.commit(divergent_machine.path, "local.txt", "Local change\n")
        divergent_machine.git("switch", "-q", "main")
        env.commit(diverged_where, "remote.txt", "Remote change\n")
        env.repo.git("push", "-q", "origin", branch, cwd=diverged_where)
        env.repo.git("fetch", "-q", "origin", branch)
        refused = divergent_machine.forge("close", diverged)
        assert refused.returncode != 0
        assert f"Local and remote work for {diverged} differ. Reconcile the branch first." in refused.stderr
        assert divergent_head != env.repo.git("rev-parse", f"origin/{branch}")
