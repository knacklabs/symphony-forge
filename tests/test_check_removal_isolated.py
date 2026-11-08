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

STORY = "FIX-CHECK-REMOVAL"


@pytest.mark.parametrize("adopted,case", [(False, case) for case in
    ("product", "setting", "addition", "workflow", "only", "test-place", "add-only")]
    + [(True, "only"), (True, "product")])
def test_1_close_isolates_removal_and_merge_waits_for_shared_checks(env, adopted, case):
    repo = env.repo
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    repo.git("switch", "-qc", "fix/setup")
    env.commit(repo.path, ".factory/fixes/setup.json", json.dumps({
        "kind": "fix", "branch": "fix/setup", "done_when": "forge.toml sets up checks"}))
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
    item, where = env.start_fix({"forge.toml": changed},
                               done_when="forge.toml removes a required check")
    if case == "product":
        env.commit(where, "product.txt", "Other work\n")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    if case == "workflow":
        workflow = ".github/workflows/forge.yml"
        env.commit(where, workflow, (where / workflow).read_text("utf-8") + "# Custom edit\n")
    env.open_pr("")
    env.checks([run("forge-pr-check"), run("new-check")])
    closed = env.close(item)
    if case in ("product", "setting", "addition", "workflow"):
        assert closed.returncode != 0
        assert "Removed checks: tests." in closed.stderr
        assert "land the removal in its own fix" in closed.stderr
        assert not env.review_calls()
        assert not env.gh_calls("pr", "create")
        return
    if case == "add-only":
        assert closed.returncode != 0
        assert "tests" in closed.stderr
        assert "Removed checks" not in closed.stderr
        return
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = repo.git("rev-parse", "HEAD", cwd=where)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Remove a check", "isDraft": False}))
    _merge_at_github(env)
    if case == "only":
        env.checks([run("forge-pr-check", None, "queued")])
        waiting = repo.forge("merge", item)
        assert waiting.returncode != 0
        assert "forge-pr-check is still queued" in waiting.stderr
        assert not env.gh_calls("pr", "merge")
        env.checks([run("forge-pr-check")])
    merged = repo.forge("merge", item)
    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert env.gh_calls("pr", "merge")
