"""An upgrade is not ready while synced files are out of date: forge close on a fix that changes
forge.toml's version refuses while the files forge sync writes differ from the fix's copies."""
from __future__ import annotations

import re

from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FORGE-UPGRADE-1"


def _sync(env, where) -> None:
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files", cwd=where)


def test_2_upgrade_is_not_ready_while_synced_files_are_out_of_date(env):
    # The default branch pins an older Forge; a fix pins the installed one and syncs, as the
    # skill's upgrade steps say, but a skill copy is left from the old release.
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    installed = re.search(r'^version = "(.+)"$', toml, re.M)[1]
    env.commit(env.repo.path, "forge.toml", toml.replace(installed, "v1.0.0"), "Pin Forge v1.0.0")
    env.repo.git("push", "-q", "origin", "main")
    # This repo was never synced, so the fix writes every synced file and needs a reason to be large.
    item, where = env.start_fix({"forge.toml": toml}, allow_large="Forge's first synced files")
    _sync(env, where)
    env.commit(where, ".claude/skills/forge/SKILL.md", "The old release's skill\n")

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr == (
        "This fix changes Forge's version, but .claude/skills/forge/SKILL.md isn't what forge "
        "sync writes for it.\n"
        f"Next: forge sync in {where}, commit what it wrote, then forge close {item}\n")
    assert "Ready" not in done.stdout
    assert env.review_calls() == []

    # Following the message makes the upgrade ready.
    _sync(env, where)
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: tidy-readme has a clean review and green checks." in done.stdout
