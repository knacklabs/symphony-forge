"""A default-branch merge delivers current guides without a manual sync."""
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401

STORY = "merge-refreshes-guide-copies"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_refreshes_guides_after_merging_templates(env, previous):
    # Contract: close publishes guides matching merged templates. A clean Git merge
    # used to leave them stale; sync's existing test never merges main. No new seam.
    repo = env.repo
    repo.git("checkout", "-q", "-b", "fix/setup-guides")
    shutil.copytree(ROOT / "src/forge", repo.path / "src/forge",
                    ignore=shutil.ignore_patterns("__pycache__"))
    settings = (repo.path / "forge.toml").read_text("utf-8") + 'repo = "forge-source"\n'
    repo.write("forge.toml", settings)
    if previous:
        fixture = ROOT / "tests/fixtures/adopted-v1.2.2/client"
        for host in (".claude", ".codex"):
            rel = f"{host}/skills/forge/SKILL.md"
            repo.write(rel, (fixture / rel).read_text("utf-8"))
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    # Fixture history includes direct main commits; sync installs real commit hooks.
    hooks = env.tmp / "fixture-hooks"
    hooks.mkdir()
    repo.git("config", "core.hooksPath", hooks.as_posix())
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Keep current generated guides")
    repo.git("checkout", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/setup-guides")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    rel = "src/forge/templates/skill.md"
    expected = (repo.path / rel).read_text("utf-8") + "\nMerged guide instruction.\n"
    env.commit(repo.path, rel, expected, "Change the guide template")
    repo.git("push", "-q", "origin", "main")
    env.gh.respond("pr", "list", "--head", stdout=
                   '[{"number":7,"state":"OPEN","body":"","isDraft":false,'
                   '"mergeStateStatus":"BEHIND"}]')

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    for host in (".claude", ".codex"):
        guide = f"{host}/skills/forge/SKILL.md"
        assert (where / guide).read_text("utf-8") == expected
        assert repo.git("show", f"origin/fix/{item}:{guide}") == expected.strip()
    assert repo.git("status", "--porcelain", cwd=where) == ""
