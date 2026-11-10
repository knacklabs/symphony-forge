"""Close catches worker guide edits before review or publication."""
import shutil
import sys

import pytest

from conftest import ROOT, FORGE_SHIM
from test_close import env  # noqa: F401
from test_ci_waits_for_busy_runners import _client

STORY = "sync-before-close"


@pytest.mark.parametrize("history", ["source", "new", "upgraded"])
def test_1_close_stops_stale_branch_guides(env, history):
    # Audit: a worker forgets sync after a template edit. Sync delivery and merge
    # coverage do not close worker template edits. Real commands need no new seam.
    repo = env.repo
    if history != "source":
        # Init or a text fixture from the earlier release supplies the client.
        # With no Forge source in the client, close must use the installed package.
        _client(env, history, "ubuntu-latest")
        expected = (repo.path / ".codex/skills/forge/SKILL.md").read_text("utf-8")
        item, where = env.start_fix()
        env.commit(where, ".codex/skills/forge/SKILL.md", "An earlier guide.\n")
    else:
        item, where, expected = _source(env)

    closed = env.close(item)  # The coordinator stays in the main checkout.

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert closed.stderr.endswith(
        f"Next: in {where.as_posix()}, run forge sync, then commit the generated guides and run close again.\n")
    assert not env.review_calls()
    assert not env.gh_calls("pr", "checks")
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".claude", ".codex"):
        assert (where / host / "skills/forge/SKILL.md").read_text("utf-8") == expected


def _source(env):
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/setup-guides")
    shutil.copytree(ROOT / "src/forge", repo.path / "src/forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8") + 'repo = "forge-source"\n')
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
    return item, where, expected
