"""An upgrade ignores Husky's generated runtime files but checks its committed Forge hooks."""
from __future__ import annotations

import json
import re
import shutil
import sys

import conftest

from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FIX-UPGRADE-UNTRACKED-HOOKS"


def test_1_untracked_hook_files_never_block_an_upgrade_but_a_stale_tracked_file_does(env):
    # Husky's dispatchers stay untracked; Forge's checks now live in committed user hooks.
    env.repo.git("config", "core.hooksPath", ".husky/_")
    toml = (env.repo.path / "forge.toml").read_text("utf-8")
    installed = re.search(r'^version = "(.+)"$', toml, re.M)[1]
    env.commit(env.repo.path, "forge.toml", toml.replace(installed, "v1.0.0"), "Pin Forge v1.0.0")
    env.repo.git("push", "-q", "origin", "main")
    prepare = ('node -e "const fs = require(\'fs\'); fs.mkdirSync(\'.husky/_\', {recursive:true}); '
               'fs.writeFileSync(\'.husky/_/h\', \'husky\')"')
    toml += f"test = {json.dumps(prepare)}\nfast_test = {json.dumps(prepare)}\n"
    item, where = env.start_fix({"forge.toml": toml}, allow_large="Forge's first synced files")
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (where / ".husky/pre-commit").exists()
    assert not (where / ".husky/_/pre-commit").exists()
    env.repo.git("add", "-A", "--", ".", ":!.husky/_", cwd=where)
    env.repo.git("commit", "-q", "-m", "Sync Forge's files", cwd=where)

    # Install-time files can also appear in close's throwaway checkout, before its status check.
    real_git = shutil.which("git")
    runtime_status = env.repo.bin / "sync-runtime-status.txt"
    conftest._install(env.repo.bin, "git", f'''#!{sys.executable}
import pathlib, subprocess, sys
args = sys.argv[1:]
result = subprocess.call([{json.dumps(real_git)}, *args])
if result == 0 and args[:2] == ["worktree", "add"] and "-b" in args:
    branch = args[args.index("-b") + 1]
    if branch.startswith("forge-synced-"):
        checkout = pathlib.Path(args[args.index("-b") + 2])
        runtime = checkout / ".husky" / "_" / "h"
        runtime.parent.mkdir(parents=True, exist_ok=True)
        runtime.write_text("husky\\n", encoding="utf-8")
        status = subprocess.check_output([{json.dumps(real_git)}, "-C", str(checkout),
            "status", "--porcelain", "--untracked-files=all"], text=True, encoding="utf-8")
        pathlib.Path({json.dumps(runtime_status.as_posix())}).write_text(status, encoding="utf-8")
sys.exit(result)
''')

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: tidy-readme has a clean review and green checks." in done.stdout
    assert "?? .husky/_/h" in runtime_status.read_text("utf-8")
    assert (where / ".husky/_/h").read_text("utf-8").strip() == "husky"
    # Later blanket commits must not adopt Husky's generated runtime file.
    (where / ".husky/_/h").unlink()

    env.commit(where, ".claude/skills/forge/SKILL.md", "The old release's skill\n")
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr.startswith("This fix changes Forge's version, but "
                                  ".claude/skills/forge/SKILL.md isn't what forge sync writes")

    # A hook file the fix does commit counts like any other: a stale one blocks close.
    env.repo.git("checkout", "-q", "HEAD~1", "--", ".claude/skills/forge/SKILL.md", cwd=where)
    env.repo.git("commit", "-q", "-m", "Restore the skill", cwd=where)
    env.commit(where, ".husky/pre-commit", "#!/bin/sh\n# The old committed hook without Forge\n")
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr.startswith("This fix changes Forge's version, but .husky/pre-commit "
                                  "isn't what forge sync writes")


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
