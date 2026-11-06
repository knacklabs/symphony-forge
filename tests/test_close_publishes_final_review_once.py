"""One close round publishes only its final reviewed commit."""
import stat
import json
import os
import sys
from pathlib import Path

import pytest

from test_close import CLEAN, FAILED, body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_close_replays_followup_after_squash_merge import stacked
from test_stacked_fixes_count_only_their_own_changes import land_on_default

STORY = "FIX-CLOSE-PUSHES-ONCE"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
@pytest.mark.parametrize("replay", [False, True, "interrupted"],
                         ids=["ordinary", "replayed-followup", "resumed-replay"])
def test_1_close_publishes_once_after_saving_review(env, previous, replay):
    if replay:
        repo, parent, _, item, where, _ = stacked(env, previous)
        repo.git("push", "-q", "origin", f"fix/{item}", cwd=where)
        land_on_default(repo, parent)
    else:
        client(env, previous)
        item, where = env.start_fix()
    updates = env.tmp / "published-heads"
    hook = Path(env.repo.git("remote", "get-url", "origin")) / "hooks" / "post-receive"
    hook.write_text(f'#!/bin/sh\ncat >> "{updates.as_posix()}"\n', encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

    if replay == "interrupted":
        env.reviews(FAILED)
        interrupted = env.close(item)
        assert interrupted.returncode == 1, interrupted.stdout + interrupted.stderr
        env.reviews(CLEAN)
    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    heads = [line.split()[1] for line in updates.read_text("utf-8").splitlines()
             if line.split()[2] == f"refs/heads/fix/{item}"]
    assert len(heads) == 1, heads
    assert heads == [env.repo.git("rev-parse", "HEAD", cwd=where)]
    assert "Review: clean" in body(env.gh_calls("pr", "create")[-1])
    for field in (".check_runs[]", ".statuses[]"):
        calls = env.gh_calls("api", "--paginate", "--jq", field)
        assert calls and all(f"/commits/{heads[0]}/" in call[-1] for call in calls)


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_2_close_requires_another_round_after_remote_work_arrives_during_review(env, previous):
    client(env, previous)
    repo = env.repo
    tests = env.tmp / "local-test-heads"
    command = f'"{Path(sys.executable).as_posix()}" client-tests.py'
    config = (repo.path / "forge.toml").read_text("utf-8")
    config = "\n".join(line for line in config.splitlines()
                       if line.partition("=")[0].strip() not in ("test", "fast_test", "test_place"))
    env.commit(repo.path, "client-tests.py", f'''import subprocess
from pathlib import Path
with Path({json.dumps(tests.as_posix())}).open("a", encoding="utf-8") as log:
    log.write(subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip() + "\\n")
''')
    env.commit(repo.path, "forge.toml", 'test_place = "local"\ntest = '
               + json.dumps(command) + "\n" + config + "\n")
    repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    repo.git("push", "-q", "origin", f"fix/{item}", cwd=where)
    outsider = env.tmp / "other-writer"
    repo.git("clone", "-q", "--branch", f"fix/{item}",
             repo.git("remote", "get-url", "origin"), str(outsider))
    incoming = env.commit(outsider, "incoming.py", "INCOMING = True\n")
    helper = Path(os.environ["AUTOREVIEW"])
    # A real second machine publishes only after the reviewer starts.
    helper.write_text(helper.read_text("utf-8").replace("args = sys.argv[1:]", f'''
subprocess.run(["git", "-C", {json.dumps(outsider.as_posix())}, "push", "-q", "origin", "fix/{item}"], check=True)
args = sys.argv[1:]
'''), encoding="utf-8")

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert "Remote work arrived after the review." in closed.stderr
    assert f"forge close {item}" in closed.stderr
    assert "Ready:" not in closed.stdout
    assert repo.git("ls-remote", "origin", f"fix/{item}").split()[0] == incoming
    assert len(tests.read_text("utf-8").splitlines()) == 1
    resumed = env.close(item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert "Ready:" in resumed.stdout
    assert len(env.review_calls()) == 2
    tested = tests.read_text("utf-8").splitlines()
    assert len(tested) == 2
    repo.git("merge-base", "--is-ancestor", incoming, tested[-1], cwd=where)
