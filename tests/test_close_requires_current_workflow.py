"""Close rejects a committed workflow that differs from sync.

Test audit: Protect close before review and push. An unchanged version used to
skip workflow validation. Existing upgrade tests miss this case. Real sync and
close own the outcome; only review and GitHub are faked. No production seam.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, FORGE_SHIM, _install
from test_close import env  # noqa: F401

STORY = "FIX-CLOSE-CATCHES-WORKFLOW-DRIFT"


@pytest.mark.parametrize("case", ["stale", "missing", "sample-data"])
def test_1_close_requires_the_workflow_that_sync_generates(env, case):
    # Missing output must fail too; sample-data sync deliberately keeps existing CI.
    if case == "sample-data":
        settings = (env.repo.path / "forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", 'stage = "prototype"\nsample_data = true\n' + settings)
        env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"app.py": "print('hello')\n"})
    if case == "sample-data":
        env.commit(where, ".github/workflows/forge.yml", "name: existing client checks\n")
        closed = env.close(item)
        assert closed.returncode == 0, closed.stdout + closed.stderr
        assert "Ready:" in closed.stdout
        return
    workflow = where / ".github/workflows/forge.yml"
    if case == "missing":
        env.repo.git("rm", ".github/workflows/forge.yml", cwd=where)
        env.repo.git("commit", "-qm", "Remove the workflow", cwd=where)
    else:
        env.commit(where, ".github/workflows/forge.yml", workflow.read_text("utf-8") + "\n# stale\n")
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Run forge sync and commit .github/workflows/forge.yml" in closed.stderr.splitlines()
    assert not env.review_calls()
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", ".github/workflows/forge.yml", cwd=where)
    env.repo.git("commit", "-qm", "Refresh workflow", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr


def source_checkout(env, command="", fast_test=""):
    """A synced source repo for close tests, with isolated hooks and real renderers."""
    repo = env.repo
    repo.git("checkout", "-q", "fix/fixture-setup")
    repo.git("merge", "-q", "--ff-only", "main")
    # Keep this a real source checkout, including the release test's renderer inputs.
    for name in repo.git("ls-files", cwd=ROOT).splitlines():
        source = ROOT / name
        if source.is_file() and not name.startswith((".factory/", "plans/")):
            target = repo.path / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    # The command under test needs the real sync test, not the source repo's other suites.
    for test in (repo.path / "tests").rglob("test_*.py"):
        if test.name != "test_release_version.py":
            test.unlink()
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'test_place = "local"\nworkers = "claude"\n'
               'checks = ["tests", "forge-pr-check"]\n'
               + (f'fast_test = {json.dumps(fast_test)}\n' if fast_test else "")
               + f'test = {json.dumps(command)}\n')
    repo.write(".forge/always-tests.txt", "")
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                  src=(repo.path / "src").as_posix()))
    repo.write(".factory/fixes/fixture-setup.json", json.dumps({"kind": "fix",
        "branch": "fix/fixture-setup", "status": "working", "why": "Prepare source",
        "done_when": "The source checkout has its generated files"}))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("config", "core.hooksPath", (env.tmp / "source-setup-hooks").as_posix())
    (repo.path / ".factory/fixes/fixture-setup.json").unlink()
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Prepare source close")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/fixture-setup")
    repo.git("push", "-q", "origin", "main")
    return version


def test_2_source_generator_changes_run_the_release_sync_test(env, monkeypatch):
    """A real source close must fail its real release sync test until regeneration.

    This replaces the receipt-only picker proof: close could skip that picker.
    The release test and sync run unchanged, with only GitHub and review faked.
    No production seam is needed.
    """
    node = "tests/test_release_version.py::test_2_release_checkout_generated_files_match_sync"
    command = f'"{Path(sys.executable).as_posix()}" -m pytest {node} -q'
    source_checkout(env, command, "forge test --pytest {base}")
    repo = env.repo
    original = (repo.path / "src/forge/prcheck.py").read_text("utf-8")
    changed = original.replace("name: forge\n", "name: regenerated-forge\n", 1)
    assert changed != original
    item, where = env.start_fix({"src/forge/prcheck.py": changed})
    # Commands and the nested release test must load the changed source worktree.
    _install(repo.bin, "forge", FORGE_SHIM.format(python=sys.executable,
                                                  src=(where / "src").as_posix()))
    monkeypatch.setenv("PYTHONPATH", str(where / "src"))
    closed = env.close(item)
    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "test_2_release_checkout_generated_files_match_sync" in closed.stdout + closed.stderr
    assert "Run forge sync and commit" in closed.stdout + closed.stderr
    assert ".github/workflows/forge.yml" in closed.stdout + closed.stderr
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=where)
    repo.git("commit", "-qm", "Regenerate source workflow", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout
