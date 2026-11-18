"""Close rejects a committed workflow that differs from sync.

Test audit: Protect close before review and push. An unchanged version used to
skip workflow validation. Existing upgrade tests miss this case. Real sync and
close own the outcome; only review and GitHub are faked. No production seam.
"""
import json
import sys
from pathlib import Path

from test_close import env  # noqa: F401

STORY = "FIX-CLOSE-CATCHES-WORKFLOW-DRIFT"


def test_1_close_requires_the_workflow_that_sync_generates(env):
    item, where = env.start_fix({"app.py": "print('hello')\n"})
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-qm", "Sync the client", cwd=where)
    workflow = where / ".github/workflows/forge.yml"
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


def test_2_source_generator_changes_run_the_release_sync_test(repo, tmp_path):
    """Selection owns which test runs; the release-sync test owns its check.

    The old picker misses generator/template changes. Existing picker tests
    miss this required node. A real pytest receipt needs no production seam.
    """
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q'
    repo.write("forge.toml", 'repo = "forge-source"\ntest = ' + json.dumps(command) + "\n")
    receipt = tmp_path / "sync-test-ran"
    repo.write("tests/test_release_version.py", "from pathlib import Path\n"
               "def test_2_release_checkout_generated_files_match_sync():\n"
               f"    Path({json.dumps(receipt.as_posix())}).touch()\n")
    repo.write("tests/test_unrelated.py", "def test_unrelated():\n    assert False\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Prepare selection fixture")
    for path in ("src/forge/prcheck.py", "src/forge/templates/brief.md"):
        base = repo.git("rev-parse", "HEAD")
        repo.write(path, "# changed\n")
        repo.git("add", path)
        repo.git("commit", "-qm", "Change workflow source")
        result = repo.forge("test", "--pytest", base)
        assert result.returncode == 0, result.stdout + result.stderr
        assert receipt.exists(), result.stdout + result.stderr
        receipt.unlink()
