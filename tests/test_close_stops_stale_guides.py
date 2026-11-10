"""Close catches worker guide edits before review or publication."""
import shutil
import sys

import pytest

from conftest import ROOT, FORGE_SHIM
from test_close import env  # noqa: F401

STORY = "sync-before-close"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_stops_stale_branch_guides(env, previous):
    # Audit: a worker forgets sync after a template edit. Sync delivery and merge
    # coverage do not close worker template edits. Real commands need no new seam.
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/setup-guides")
    shutil.copytree(ROOT / "src/forge", repo.path / "src/forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8") + 'repo = "forge-source"\n')
    if previous:
        fixture = ROOT / "tests/fixtures/adopted-v1.2.2/client"
        for host in (".claude", ".codex"):
            rel = f"{host}/skills/forge/SKILL.md"
            repo.write(rel, (fixture / rel).read_text("utf-8"))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    hooks = env.tmp / "fixture-hooks"
    hooks.mkdir()
    repo.git("config", "core.hooksPath", hooks.as_posix())
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Keep generated guides")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/setup-guides")
    repo.git("push", "-q", "origin", "main")
    rel = "src/forge/templates/skill.md"
    expected = (repo.path / rel).read_text("utf-8") + "\nWorker guide instruction.\n"
    item, where = env.start_fix({rel: expected})
    (repo.bin / "forge").write_text(
        FORGE_SHIM.format(python=sys.executable, src=str(where / "src")), encoding="utf-8")

    closed = env.close(item)

    assert closed.returncode != 0, closed.stdout + closed.stderr
    assert "forge sync" in closed.stdout + closed.stderr
    assert "then commit" in closed.stdout + closed.stderr
    assert not env.review_calls()
    assert not env.gh_calls("pr", "checks")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".claude", ".codex"):
        assert (where / host / "skills/forge/SKILL.md").read_text("utf-8") == expected
