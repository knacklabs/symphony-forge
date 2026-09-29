"""An upgrade is not ready while synced files are out of date: forge close on a fix that changes
forge.toml's version refuses while the files forge sync writes differ from the fix's copies."""
from __future__ import annotations

import re

from test_close import env  # noqa: F401 (the shared fixture)

STORY = "FORGE-UPGRADE-1"


def _sync(env, where) -> None:
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr


def _commit(env, where) -> None:
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
    _commit(env, where)
    env.commit(where, ".claude/skills/forge/SKILL.md", "The old release's skill\n")

    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr == (
        "This fix changes Forge's version, but .claude/skills/forge/SKILL.md isn't what forge "
        "sync writes for it.\n"
        f"Next: forge sync in {where}, commit what it wrote, then forge close {item}\n")
    assert "Ready" not in done.stdout
    assert env.review_calls() == []

    # Close pushes the commit, so a sync that isn't committed yet doesn't count.
    _sync(env, where)
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert "SKILL.md isn't what forge sync writes" in done.stderr
    assert env.review_calls() == []

    # Committing what sync wrote makes the upgrade ready.
    _commit(env, where)
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: tidy-readme has a clean review and green checks." in done.stdout

    # The review close recorded, after its throwaway sync checkout, is the one forge-pr-check
    # finds current on the same head.
    head = env.repo.git("rev-parse", "HEAD", cwd=where)
    base = env.repo.git("merge-base", "origin/main", head, cwd=where)
    done = env.repo.forge("hook", "pr-check", "--base", base, "--head", head,
                          "--branch", "fix/tidy-readme", cwd=where)
    assert (done.returncode, done.stdout) == (0, "forge-pr-check passed for fix/tidy-readme.\n"), \
        done.stderr

    # A file sync deletes counts too: an old Forge-only CLAUDE.md that sync removed in the folder
    # but that is still committed stays in the pull request.
    env.commit(where, "CLAUDE.md", "@AGENTS.md\n", "The old release's CLAUDE.md")
    _sync(env, where)
    assert not (where / "CLAUDE.md").exists()
    reviews = len(env.review_calls())
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 1
    assert done.stderr.startswith("This fix changes Forge's version, but CLAUDE.md isn't what "
                                  "forge sync writes for it.\n")
    assert len(env.review_calls()) == reviews

    _commit(env, where)
    done = env.repo.forge("close", item, cwd=where)

    assert done.returncode == 0, done.stdout + done.stderr
    assert "Ready: tidy-readme has a clean review and green checks." in done.stdout

    # Only the Forge the fix pins can call it synced: once the synced upgrade has landed on the
    # default branch and the fix then pins a newer release, close run from the default checkout
    # passes the pin check there, but the installed Forge can't know what the newer one writes.
    # GitHub's merge moves the default branch on the remote, where no local hook runs.
    origin = env.repo.git("remote", "get-url", "origin")
    env.repo.git("update-ref", "refs/heads/main", "refs/heads/fix/tidy-readme", cwd=origin)
    env.repo.git("fetch", "-q", "origin")
    env.repo.git("merge", "-q", "--ff-only", "origin/main")
    env.commit(where, "forge.toml", toml.replace(installed, "v9.9.9"), "Pin Forge v9.9.9")
    reviews = len(env.review_calls())

    done = env.repo.forge("close", item, cwd=env.repo.path)

    assert done.returncode == 1, done.stdout + done.stderr
    assert done.stderr == (
        f"This fix pins Forge v9.9.9, but Forge {installed} is running close, so it can't tell "
        "whether the fix's files are what v9.9.9 writes.\n"
        "Next: uv tool install git+https://github.com/knacklabs/symphony-forge@v9.9.9, then "
        f"forge close {item}\n")
    assert "Ready" not in done.stdout
    assert len(env.review_calls()) == reviews
