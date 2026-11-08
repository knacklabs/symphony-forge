"""Check removal is isolated at close and keeps merge possible.

Audit: named settings tests never remove checks. These real command cases
protect refusal before review and admission with the removed check absent.
Only external services are faked; no production test seam is needed.
"""
import json
import shutil

import pytest

from conftest import ROOT
from test_close import env, run  # noqa: F401
from test_merge_command import _merge_at_github
from test_spotted import entry

STORY = "FIX-CHECK-REMOVAL"


@pytest.mark.parametrize("adopted,case", [(False, case) for case in
    ("product", "setting", "addition", "workflow", "only", "test-place", "add-only",
     "npm-workflow", "pnpm-workflow", "behind", "main-check", "spotted", "planning-record", "conflict", "remote")]
    + [(True, "only"), (True, "product"), (True, "legacy-spotted")])
def test_1_close_isolates_removal_and_merge_waits_for_shared_checks(env, adopted, case):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/setup")
    env.commit(repo.path, ".factory/fixes/setup.json", json.dumps({
        "kind": "fix", "branch": "fix/setup", "done_when": "forge.toml sets up checks"}))
    if case in ("npm-workflow", "pnpm-workflow"):
        env.commit(repo.path, "package.json", '{"name": "client", "private": true}\n')
        lockfile = "package-lock.json" if case == "npm-workflow" else "pnpm-lock.yaml"
        env.commit(repo.path, lockfile, "{}\n" if lockfile.endswith("json") else "lockfileVersion: '9.0'\n")
    settings = (f'version = "{version}"\nworkers = "claude"\nmerge = "agent"\n'
                'test = "echo ok"\nfast_test = "echo ok"\ntest_place = "ci"\n'
                'checks = ["tests", "forge-pr-check"]\n')
    env.commit(repo.path, "forge.toml", settings)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Sync settings")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/setup")
    repo.git("fetch", "-q", str(repo.path), "main:main",
             cwd=repo.git("remote", "get-url", "origin"))
    repo.git("fetch", "-q", "origin", "main")
    names = ('["tests", "forge-pr-check", "new-check"]' if case == "add-only" else
             '["forge-pr-check", "new-check"]' if case == "addition" else '["forge-pr-check"]')
    changed = settings.replace('["tests", "forge-pr-check"]', names)
    if case == "setting":
        changed = changed.replace('echo ok', 'echo changed')
    if case == "test-place":
        changed = changed.replace('test_place = "ci"', 'test_place = "local"')
    item, where = env.start_fix({"app.py": "print('hello')\n"} if case == "main-check" else {"forge.toml": changed},
                               done_when="forge.toml removes a required check")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "--allow-empty", "-qm", "Sync branch workflows", cwd=where)
    if case == "workflow":
        workflow = ".github/workflows/forge.yml"
        env.commit(where, workflow, (where / workflow).read_text("utf-8") + "# Custom edit\n")
    if case in ("behind", "main-check", "conflict"):
        owner = env.tmp / "owner"
        repo.git("clone", "-q", repo.git("remote", "get-url", "origin"), str(owner))
        if case == "main-check":
            env.commit(owner, "forge.toml", settings.replace('"tests",', '"main-check", "tests",'))
        else:
            env.commit(owner, "product.txt" if case == "conflict" else "incoming.txt", "Main work\n")
        repo.git("push", "-q", "origin", "main", cwd=owner)
    if case == "spotted":
        repo.git("commit", "--allow-empty", "-qm", "Note a separate issue\n\nSpotted: bug README.md:1 A separate issue.", cwd=where)
    if case == "legacy-spotted":
        # A prior release saved its review observation in the shared list.
        env.commit(where, "plans/spotted.json", json.dumps({"items": [
            entry("bug", "README.md", 1, "A separate issue.", "review")]}))
    if case == "planning-record":
        env.commit(where, "plans/notes.md", "A planning note.\n")
    if case in ("product", "conflict", "remote"):
        branch = repo.git("branch", "--show-current", cwd=where)
        repo.git("push", "-q", "origin", branch, cwd=where)
        remote_head = repo.git("ls-remote", "--heads", "origin", f"refs/heads/{branch}").split()[0]
        if case in ("product", "conflict"):
            env.commit(where, "product.txt", "Other work\n")
            assert repo.git("rev-parse", "HEAD", cwd=where) != remote_head
        if case == "remote":
            collaborator = env.tmp / "collaborator"
            repo.git("clone", "-q", "--branch", branch, repo.git("remote", "get-url", "origin"), str(collaborator))
            remote_head = env.commit(collaborator, "product.txt", "Collaborator work\n")
            repo.git("push", "-q", "origin", branch, cwd=collaborator)
    env.open_pr("")
    if case == "test-place":
        env.checks([run("tests"), run("forge-pr-check", None, "queued")])
    elif case == "add-only":
        env.checks([run("tests"), run("forge-pr-check")])
    elif case == "main-check":
        env.checks([run("tests"), run("forge-pr-check"), run("main-check")])
    else:
        env.checks([run("forge-pr-check"), run("new-check")])
    closed = env.close(item)
    if case in ("product", "setting", "addition", "workflow", "conflict", "remote"):
        assert closed.returncode != 0
        assert "Removed checks: tests." in closed.stderr
        assert "land the removal in its own fix" in closed.stderr
        if case in ("product", "conflict", "remote"):
            assert repo.git("ls-remote", "--heads", "origin", f"refs/heads/{branch}").split()[0] == remote_head
        assert not env.review_calls()
        assert not env.gh_calls("pr", "create")
        return
    if case == "add-only":
        assert closed.returncode != 0
        assert "new-check" in closed.stderr
        assert "Removed checks" not in closed.stderr
        assert "Ready:" not in closed.stdout
        env.checks([run("tests"), run("forge-pr-check"), run("new-check")])
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        return
    if case in ("npm-workflow", "pnpm-workflow", "behind", "main-check", "spotted", "legacy-spotted", "planning-record"):
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Ready:" in closed.stdout
        return
    if case == "test-place":
        assert closed.returncode != 0
        assert "forge-pr-check is still queued" in closed.stderr
        assert "Ready:" not in closed.stdout
        assert not env.gh_calls("pr", "create")
        env.checks([run("tests"), run("forge-pr-check")])
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Remove a check", "isDraft": False}))
    _merge_at_github(env)
    if case == "only" and not adopted:
        # No reported checks: an empty required list would incorrectly merge.
        env.checks([])
        missing = repo.forge("merge", item)
        assert missing.returncode != 0
        assert "forge-pr-check has not reported" in missing.stderr
        assert not env.gh_calls("pr", "merge")
    if case in ("only", "test-place"):
        env.checks([run("forge-pr-check", None, "queued")])
        waiting = repo.forge("merge", item)
        assert waiting.returncode != 0
        assert "forge-pr-check is still queued" in waiting.stderr
        assert not env.gh_calls("pr", "merge")
        env.checks([run("forge-pr-check")])
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert env.gh_calls("pr", "merge")
