"""An upgrade's synced-files check skips the hook files forge sync writes into a husky repo's
.husky/_, which are never committed, while a stale or missing synced file still blocks close."""
from __future__ import annotations

import re

from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FIX-UPGRADE-UNTRACKED-HOOKS"


def test_1_untracked_hook_files_never_block_an_upgrade_but_a_stale_tracked_file_does(env):
    # A husky repo: git's hooks live in .husky/_ inside each checkout, which husky's install fills
    # and git ignores, and the repo's test command rewrites husky's hook helper there.
    env.repo.git("config", "core.hooksPath", ".husky/_")
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    installed = re.search(r'^version = "(.+)"$', toml, re.M)[1]
    env.commit(env.repo.path, "forge.toml", toml.replace(installed, "v1.0.0"), "Pin Forge v1.0.0")
    env.repo.git("push", "-q", "origin", "main")
    toml += 'test = "echo husky > .husky/_/h"\n'
    item, where = env.start_fix({"forge.toml": toml}, allow_large="Forge's first synced files")
    (where / ".husky/_").mkdir(parents=True)
    (where / ".husky/_/.gitignore").write_text("*\n", "utf-8")
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files", cwd=where)

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: tidy-readme has a clean review and green checks." in done.stdout
    assert (where / ".husky/_/h").read_text("utf-8").strip() == "husky"

    env.commit(where, ".claude/skills/forge/SKILL.md", "The old release's skill\n")
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr.startswith("This fix changes Forge's version, but "
                                  ".claude/skills/forge/SKILL.md isn't what forge sync writes")


def test_2_a_new_synced_file_the_upgrade_did_not_commit_blocks_close(env):
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    installed = re.search(r'^version = "(.+)"$', toml, re.M)[1]
    env.commit(env.repo.path, "forge.toml", toml.replace(installed, "v1.0.0"), "Pin Forge v1.0.0")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix({"forge.toml": toml}, allow_large="Forge's first synced files")
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.repo.git("add", "-A", cwd=where)
    env.repo.git("reset", "-q", "--", ".claude/skills/forge/SKILL.md", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files but one", cwd=where)

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr.startswith("This fix changes Forge's version, but "
                                  ".claude/skills/forge/SKILL.md isn't what forge sync writes")
