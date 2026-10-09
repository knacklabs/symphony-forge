"""src/forge/merge.py guards the item's change, and tidies completed merges."""
import json
import shutil
import subprocess
import sys

import pytest

from conftest import ROOT, patient
from test_close import GREEN, env  # noqa: F401
from test_merge_command import _merge_at_github

STORY = "merge-guard-base"


def _ready_before_switch(env, adopted=False, changes_setting=False):
    repo = env.repo
    if adopted:
        patient(lambda: shutil.copytree(
            ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True))
        settings = (repo.path / "forge.toml").read_text("utf-8")
        assert 'version = "v1.2.2"' in settings
        version = repo.forge("--version").stdout.split()[-1]
        # The earlier adoption's settings survive upgrading the pin.
        env.commit(repo.path, "forge.toml", settings.replace("v1.2.2", version))
        repo.git("push", "-q", "origin", "main")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    changes = {"forge.toml": settings.replace('merge = "human"', 'merge = "agent"')
               if 'merge = "human"' in settings else 'merge = "agent"\n' + settings}
    item, where = env.start_fix(changes if changes_setting else None)
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    env.commit(where, "README.md", "# Hello\n")
    env.open_pr("")
    env.checks(GREEN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = repo.git("rev-parse", "HEAD", cwd=where)
    # The owner's default-branch change lands outside the worker's installed hooks.
    owner = env.tmp / "owner-switch"
    repo.git("clone", "-q", str(env.tmp / "remote.git"), str(owner))
    env.commit(owner, "forge.toml", changes["forge.toml"])
    repo.git("push", "-q", "origin", "main", cwd=owner)
    env.gh.respond("pr", "view", stdout=json.dumps({
        "number": 7, "state": "OPEN", "baseRefName": "main", "headRefOid": head,
        "headRefName": "fix/tidy-readme", "title": "Tidy readme", "isDraft": False}))
    return item, where, head


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_ready_branch_predating_agent_merges_merges(env, adopted):
    item, where, _ = _ready_before_switch(env, adopted)
    _merge_at_github(env)

    merged = env.repo.forge("merge", item)

    assert merged.returncode == 0, merged.stdout + merged.stderr
    assert env.gh_calls("pr", "merge")
    assert env.repo.git("show", "origin/main:app.py") == "print('hello')"
    assert not where.exists()


def test_2_item_changing_merge_value_is_refused_even_when_default_matches(env):
    item, where, _ = _ready_before_switch(env, changes_setting=True)

    refused = env.repo.forge("merge", item)

    assert refused.returncode != 0
    assert refused.stderr == (
        f"{item} changes the merge setting in forge.toml, so only the repo owner merges its pull request.\n"
        "Next: the repo owner merges its pull request, then forge next\n")
    assert not env.gh_calls("pr", "merge")
    assert where.exists()


@pytest.mark.parametrize("changes_setting", [False, True], ids=["older-branch", "changed-setting"])
@pytest.mark.parametrize("local_work", ["", "unsaved.txt", ".hooks/keep.txt", ".hooks/pre-commit"],
                         ids=["generated-hooks", "unsaved-file", "user-hook-file", "edited-shim"])
def test_3_already_merged_item_tidies_without_setting_guard(env, local_work, changes_setting):
    item, where, head = _ready_before_switch(env, changes_setting=changes_setting)
    _merge_at_github(env)
    subprocess.run([sys.executable, str(env.repo.bin / "gh"), "pr", "merge", "7", "--squash",
                    "--subject", "Tidy readme", "--match-head-commit", head],
                   cwd=env.repo.path, check=True, capture_output=True)
    # Husky's rebuilt hook folder is disposable and ignored, as its real installer creates it.
    hooks = where / ".husky" / "_"
    hooks.mkdir(parents=True)
    (hooks / ".gitignore").write_text("*", encoding="utf-8")
    (hooks / "pre-commit").write_text('#!/usr/bin/env sh\n. "$(dirname "$0")/h"', encoding="utf-8")
    env.repo.git("config", "core.hooksPath", ".hooks", cwd=where)
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    assert (where / ".hooks/pre-commit").is_file()
    if local_work:
        (where / local_work).write_text("Keep this work\n", encoding="utf-8")
    calls = len(env.gh_calls("pr", "merge"))

    tidied = env.repo.forge("merge", item)

    assert tidied.returncode == 0, tidied.stdout + tidied.stderr
    assert len(env.gh_calls("pr", "merge")) == calls
    assert where.exists() == bool(local_work)
    if local_work:
        assert (where / local_work).read_text("utf-8") == "Keep this work\n"
    else:
        assert not env.repo.git("branch", "--list", "fix/tidy-readme")
        assert not (env.repo.path / ".git/forge/ready" / f"{item}.json").exists()
