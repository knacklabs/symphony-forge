"""src/forge/merge.py rebuilds an interrupted owner switch on the upgraded default branch."""
import json
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import conftest
from test_close import GREEN, env  # noqa: F401
from test_merge_enable import (BRANCH, READY, TAKEN, FAIL_SETTING_COMMIT, enable, hook,
                               owner, raw, set_main, worktree)  # noqa: F401
from test_setup import _fresh_client
from test_upgrade_command import NAME, RELEASE, install, unsynced_up  # noqa: F401

STORY = "merge-enable-stale"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
@pytest.mark.parametrize("interruption", ["before commit", "after push"])
def test_1_merge_enable_rebuilds_same_fix_on_upgraded_default(unsynced_up, monkeypatch,
                                                           adopted, interruption):
    up, repo = unsynced_up, unsynced_up.repo
    monkeypatch.delenv("CODEX_THREAD_ID")
    if adopted:
        conftest.patient(lambda: shutil.copytree(
            conftest.ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True))
    else:
        client, initialized = _fresh_client(repo, up.env.gh, up.tmp)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
        up.env.checks(GREEN)
    # Adopted settings really pin the earlier release; its launcher runs the command
    # code with that release identity. Only the installer and GitHub/review are fake.
    settings = (repo.path / "forge.toml").read_text("utf-8")
    if not adopted:
        settings = 'merge = "human"\n' + settings
    current = repo.forge("--version").stdout.split()[-1]
    up.on_main("forge.toml", settings.replace(current, "v1.2.2"))
    installed = up.tmp / "uvbin" / "forge"
    subprocess.run([sys.executable, str(repo.bin / "uv"), *install("v1.2.2")],
                   check=True, capture_output=True)
    repo.git("switch", "-qc", "fix/adoption")
    repo.write(".factory/fixes/adoption.json", json.dumps({
        "kind": "fix", "branch": "fix/adoption", "status": "working",
        "why": "Adopt Forge", "done_when": "Forge is adopted"}))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt Forge")
    repo.git("push", "-q", "origin", "fix/adoption")
    remote = repo.git("remote", "get-url", "origin")
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", "HEAD"), cwd=remote)
    repo.git("switch", "-q", "main")
    repo.git("fetch", "-q", "origin", "main")
    repo.git("merge", "-q", "--ff-only", "origin/main")

    def owner_enable():
        return subprocess.run([sys.executable, str(installed), "merge", "enable"], cwd=repo.path,
                              capture_output=True, text=True, timeout=60)

    if interruption == "before commit":
        hook(up.env, "pre-commit", FAIL_SETTING_COMMIT)
    else:
        up.env.gh.respond("pr", "create", stderr="GitHub is down", exit=1)
    stopped = owner_enable()
    assert stopped.returncode != 0, stopped.stdout + stopped.stderr
    where = worktree(up.env)
    assert b'merge = "agent"' in (where / "forge.toml").read_bytes()
    old_head = repo.git("rev-parse", BRANCH)
    if interruption == "before commit":
        hook(up.env, "pre-commit", None)
    else:
        up.env.gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")

    upgraded = up.run(RELEASE)
    assert upgraded.returncode == 0, upgraded.stdout + upgraded.stderr
    # Land the owner's upgrade, as GitHub would; the merge switch remains unmerged.
    repo.git("push", "-q", "origin", f"fix/{NAME}:refs/heads/upgraded")
    repo.git("update-ref", "refs/heads/main", repo.git("rev-parse", f"fix/{NAME}"), cwd=remote)
    repo.git("fetch", "-q", "origin", "main")
    repo.git("merge", "-q", "--ff-only", "origin/main")
    default_head, before = repo.git("rev-parse", "origin/main"), raw(up.env, "origin/main")

    resumed = owner_enable()

    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert resumed.stdout.splitlines()[-2:] == READY
    assert worktree(up.env) == where
    assert raw(up.env, f"origin/{BRANCH}") == before.replace(b'merge = "human"', b'merge = "agent"')
    assert repo.git("merge-base", BRANCH, "origin/main") == default_head
    assert not repo.git("rev-list", "--merges", f"origin/main..{BRANCH}")
    assert repo.git("merge-base", BRANCH, old_head) != old_head
    assert repo.git("rev-parse", "origin/main") == default_head
    assert raw(up.env, "origin/main") == before
    assert not up.env.gh_calls("pr", "merge")
    assert repo.git("status", "--porcelain", cwd=where) == ""


@pytest.mark.parametrize("other_work", ["another file", "staged setting"])
def test_2_merge_enable_leaves_other_work_untouched_before_rebuilding(owner, other_work):
    hook(owner, "pre-commit", FAIL_SETTING_COMMIT)
    assert enable(owner).returncode != 0
    hook(owner, "pre-commit", None)
    where, repo = worktree(owner), owner.repo
    config = (where / "forge.toml").read_bytes()
    if other_work == "another file":
        owner.commit(where, "other.toml", 'merge = "agent"\n')
    else:
        (where / "forge.toml").write_bytes(config.replace(b'workers = "claude"', b'workers = "codex"'))
        repo.git("add", "forge.toml", cwd=where)
        (where / "forge.toml").write_bytes(config)
    set_main(owner, (repo.path / "forge.toml").read_text("utf-8") + "# Default moved\n")
    before = (repo.git("rev-parse", "HEAD", cwd=where),
              repo.git("status", "--porcelain", cwd=where),
              repo.git("diff", "--cached", cwd=where))

    refused = enable(owner)

    assert refused.returncode != 0
    assert refused.stderr == TAKEN
    assert before == (repo.git("rev-parse", "HEAD", cwd=where),
                      repo.git("status", "--porcelain", cwd=where),
                      repo.git("diff", "--cached", cwd=where))
    assert (where / "forge.toml").read_bytes() == config
    assert not owner.gh_calls("pr", "create")


@pytest.mark.parametrize("default_moved", [False, True], ids=["without-rebuild", "with-rebuild"])
@pytest.mark.parametrize("remote_work", ["file", "reverted file"])
def test_3_merge_enable_preserves_fetched_remote_work(owner, default_moved, remote_work):
    owner.gh.respond("pr", "create", stderr="GitHub is down", exit=1)
    assert enable(owner).returncode != 0
    repo, where = owner.repo, worktree(owner)
    other = owner.tmp / "another-checkout"
    repo.git("worktree", "add", "-qb", "remote-work", str(other), BRANCH)
    owner.commit(other, "remote.txt", "Work from another checkout\n")
    if remote_work == "reverted file":
        repo.git("revert", "--no-edit", "HEAD", cwd=other)
    repo.git("push", "-q", "origin", f"remote-work:{BRANCH}", cwd=other)
    repo.git("fetch", "-q", "origin")
    remote_head = repo.git("rev-parse", f"origin/{BRANCH}")
    if default_moved:
        set_main(owner, (repo.path / "forge.toml").read_text("utf-8") + "# Default moved\n")
    before = (repo.git("rev-parse", BRANCH), repo.git("status", "--porcelain", cwd=where),
              (where / "forge.toml").read_bytes())

    refused = enable(owner)

    assert refused.returncode != 0
    assert refused.stderr == TAKEN
    assert before == (repo.git("rev-parse", BRANCH), repo.git("status", "--porcelain", cwd=where),
                      (where / "forge.toml").read_bytes())
    assert repo.git("ls-remote", "--heads", "origin", BRANCH).split()[0] == remote_head


@pytest.mark.parametrize("race", [False, True], ids=["safe-remote-history", "remote-moves-after-validation"])
def test_4_merge_enable_publishes_only_against_the_validated_remote_tip(owner, race):
    owner.gh.respond("pr", "create", stderr="GitHub is down", exit=1)
    assert enable(owner).returncode != 0
    owner.gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/7\n")
    repo = owner.repo
    other = owner.tmp / "another-checkout"
    repo.git("worktree", "add", "-qb", "remote-work", str(other), BRANCH)
    repo.git("commit", "-q", "--allow-empty", "-m", "Retry the merge switch", cwd=other)
    repo.git("push", "-q", "origin", f"remote-work:{BRANCH}", cwd=other)
    set_main(owner, (repo.path / "forge.toml").read_text("utf-8") + "# Default moved\n")
    default_head = repo.git("rev-parse", "origin/main")
    if race:
        racing_head = owner.commit(other, "remote.txt", "Keep this remote work\n")
        repo.git("push", "-q", "origin", "remote-work", cwd=other)
        remote = shlex.quote(Path(repo.git("remote", "get-url", "origin")).as_posix())
        # The real commit hook moves and fetches the remote after validation, before push.
        hook(owner, "pre-commit", f"#!/bin/sh\ngit --git-dir={remote} update-ref "
             f"refs/heads/{BRANCH} {racing_head}\ngit fetch -q origin {BRANCH}\n")

    resumed = enable(owner)

    if race:
        assert resumed.returncode != 0
        assert "stale info" in resumed.stderr, resumed.stdout + resumed.stderr
        assert not owner.review_calls()
        assert repo.git("ls-remote", "--heads", "origin", BRANCH).split()[0] == racing_head
        assert repo.git("show", f"{racing_head}:remote.txt") == "Keep this remote work"
    else:
        assert resumed.returncode == 0, resumed.stdout + resumed.stderr
        assert resumed.stdout.splitlines()[-2:] == READY
        assert repo.git("merge-base", BRANCH, "origin/main") == default_head
        before = raw(owner, "origin/main")
        ending = b"\r\n" if b"\r\n" in before else b"\n"
        assert raw(owner, f"origin/{BRANCH}") == b'merge = "agent"' + ending + before
    assert repo.git("rev-parse", "origin/main") == default_head
    assert not owner.gh_calls("pr", "merge")


@pytest.mark.parametrize("location", ["working tree", "index", "remote", "reverted remote"])
def test_5_merge_enable_preserves_merge_text_inside_a_multiline_setting(owner, location):
    repo = owner.repo
    settings = 'merge = "human"\n' + (repo.path / "forge.toml").read_text("utf-8")
    settings += "test = '''python -c \"\nmerge = [1]\nprint(merge)\n\"'''\n"
    set_main(owner, settings)
    owner.gh.respond("pr", "create", stderr="GitHub is down", exit=1)
    stopped = enable(owner)
    assert stopped.returncode != 0
    assert "GitHub is down" in stopped.stderr
    where = worktree(owner)
    original = (where / "forge.toml").read_bytes()
    edited = original.replace(b"merge = [1]", b"merge = [2]")
    if location in ("remote", "reverted remote"):
        other = owner.tmp / "multiline-checkout"
        repo.git("worktree", "add", "-qb", "multiline-work", str(other), BRANCH)
        owner.commit(other, "forge.toml", edited.decode("utf-8"))
        if location == "reverted remote":
            repo.git("revert", "--no-edit", "HEAD", cwd=other)
        repo.git("push", "-q", "origin", f"multiline-work:{BRANCH}", cwd=other)
        repo.git("fetch", "-q", "origin")
    else:
        (where / "forge.toml").write_bytes(edited)
        if location == "index":
            repo.git("add", "forge.toml", cwd=where)
            (where / "forge.toml").write_bytes(original)
    set_main(owner, settings + "# Default moved\n")
    before = (repo.git("rev-parse", BRANCH), (where / "forge.toml").read_bytes(),
              repo.git("diff", "--cached", cwd=where),
              repo.git("ls-remote", "--heads", "origin", BRANCH))

    refused = enable(owner)

    assert refused.returncode != 0
    assert refused.stderr == TAKEN
    assert before == (repo.git("rev-parse", BRANCH), (where / "forge.toml").read_bytes(),
                      repo.git("diff", "--cached", cwd=where),
                      repo.git("ls-remote", "--heads", "origin", BRANCH))
