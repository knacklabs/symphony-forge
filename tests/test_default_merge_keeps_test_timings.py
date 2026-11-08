"""Default merges preserve parallel timing updates without a repair round.

Audit: real close/work commands exercise src/forge/merge_timings.py. Existing
conflict tests have no timing-file collision. Removing automatic resolution
fails the union assertion; no production test seam is needed.
"""
import json
import shutil
import subprocess
import sys

import pytest

from test_close import GREEN, env  # noqa: F401
from test_upgrade_command import Upgrade
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401
from conftest import _install
from test_last_task_records_story_outcome import github_merge
from test_stack_start import configured, start

STORY = "merge-test-timings-union"


def _parallel_timings(env, client, other=False):
    # Fresh init supplies a generic GitHub API answer; close needs check runs.
    env.checks(GREEN)
    setup = Upgrade(env, env.tmp)
    setup.on_main(".test_durations", json.dumps({"shared": 1}))
    setup.on_main("app.py", "base\n")
    item, folder = env.start_fix({
        ".test_durations": json.dumps({"shared": 2, "worker": 3}),
        "app.py": "worker\n",
    })
    before = client.git("rev-parse", "HEAD", cwd=folder)
    setup.on_main(".test_durations", json.dumps({"shared": 4, "default": 5}))
    if other:
        setup.on_main("app.py", "default\n")
    return item, folder, before


@pytest.mark.parametrize("client, command, other", [
    (False, "close", False), (False, "work", False),
    (False, "close", True), (False, "work", True),
    (True, "close", False),
], indirect=["client"])
def test_1_default_merge_resolves_only_test_timings(env, client, command, other):
    item, folder, before = _parallel_timings(env, client, other)
    incoming = client.git("rev-parse", "main")
    if command == "work":
        log = install_claude(client)
    result = client.forge(command, item)
    output = result.stdout + result.stderr
    if other:
        if command == "close":
            assert result.returncode == 1, output
            assert "conflicts in .test_durations, app.py" in output
            assert client.git("rev-parse", "HEAD", cwd=folder) == before
        else:
            assert "First, finish the merge of origin/main" in calls(log)[-1]["brief"]
        assert (folder / ".test_durations").read_text("utf-8") == json.dumps({"shared": 2, "worker": 3})
    else:
        assert result.returncode == 0, output
        assert "First, finish the merge" not in output
        if command == "work":
            assert "First, finish the merge" not in calls(log)[-1]["brief"]
        expected = {"default": 5, "shared": 4, "worker": 3}
        assert (folder / ".test_durations").read_text("utf-8") == json.dumps(expected, indent=4, sort_keys=True) + "\n"
        client.git("merge-base", "--is-ancestor", incoming, "HEAD", cwd=folder)
        client.git("merge-base", "--is-ancestor", before, "HEAD", cwd=folder)
    assert client.git("diff", "--name-only", "--diff-filter=U", cwd=folder) == ""


@pytest.mark.platform
@pytest.mark.parametrize("client, command", [(False, "close"), (False, "work")], indirect=["client"])
def test_2_rejected_timing_merge_commit_leaves_no_half_merge(env, client, command):
    # Contract: a real rejecting Git hook leaves the command's normal repair
    # path usable. The older collision cases never reject the merge commit.
    item, folder, before = _parallel_timings(env, client)
    _install(client.bin, "pre-commit", f"#!{sys.executable}\n"
             "import subprocess, sys\n"
             "sys.exit(subprocess.run(['git', 'rev-parse', '-q', '--verify', 'MERGE_HEAD'], "
             "capture_output=True).returncode == 0)\n")
    client.git("config", "core.hooksPath", client.bin.as_posix())
    if command == "work":
        log = install_claude(client)
    result = client.forge(command, item)
    pending = subprocess.run(["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
                             cwd=folder, capture_output=True)
    assert pending.returncode != 0, result.stdout + result.stderr
    assert (folder / ".test_durations").read_text("utf-8") == json.dumps({"shared": 2, "worker": 3})
    if command == "close":
        assert result.returncode == 1
        assert "conflicts in .test_durations" in result.stderr
        assert client.git("rev-parse", "HEAD", cwd=folder) == before
    else:
        assert result.returncode == 0, result.stdout + result.stderr
        assert calls(log)[-1]["brief"].startswith("First, finish the merge of origin/main")
        again = client.forge("work", item)
        assert again.returncode == 0, again.stdout + again.stderr
        assert "First, finish the merge of origin/main" in calls(log)[-1]["brief"]


def test_3_stacked_close_keeps_timings_after_parent_squash_merge(env):
    # Contract: replay keeps parent and child code while resolving timing data.
    # Ordinary fixes do not enter the replay path. GitHub alone is faked.
    repo = configured(env, False)
    parent, _ = start(repo, "A")
    env.commit(parent, "app.py", "A_VALUE = 1\n")
    env.commit(parent, ".test_durations", json.dumps({"shared": 1, "parent": 6}))
    closed = env.close("STACK/A")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    child, _ = start(repo, "B")
    env.commit(child, "use.py", "B_VALUE = 1\n")
    env.commit(child, ".test_durations", json.dumps({"shared": 2, "parent": 6, "worker": 3}))
    env.gh.respond("pr", "create", stdout="https://github.com/acme/shop/pull/8\n")
    closed = env.close("STACK/B")
    assert closed.returncode == 0, closed.stdout + closed.stderr
    env.gh.respond("pr", "list", "--base", "task/STACK-A", stdout=json.dumps([
        {"number": 8, "headRefName": "task/STACK-B"}]))
    github_merge(env, "task/STACK-A")
    merged = repo.forge("merge", "STACK/A")
    assert merged.returncode == 0, merged.stdout + merged.stderr
    env.gh.respond("pr", "list", "--head", "task/STACK-B", "--state", "all", stdout=json.dumps([
        {"number": 8, "state": "OPEN", "body": "", "isDraft": False, "baseRefName": "main"}]))
    (repo.bin / "github-merged").unlink()
    shutil.rmtree(repo.bin / "github-merge")
    github_merge(env, "task/STACK-B")
    repo.git("fetch", "-q", "origin", "main")
    repo.git("merge", "-q", "--ff-only", "origin/main")
    Upgrade(env, env.tmp).on_main(".test_durations", json.dumps({"shared": 4, "parent": 6, "default": 5}))
    result = env.close("STACK/B")
    assert result.returncode == 0, result.stdout + result.stderr
    assert (child / ".test_durations").read_text("utf-8") == json.dumps(
        {"default": 5, "parent": 6, "shared": 4, "worker": 3}, indent=4, sort_keys=True) + "\n"
    assert (child / "app.py").read_text("utf-8") == "A_VALUE = 1\n"
    assert (child / "use.py").read_text("utf-8") == "B_VALUE = 1\n"
    repo.git("merge-base", "--is-ancestor", "origin/main", "HEAD", cwd=child)
