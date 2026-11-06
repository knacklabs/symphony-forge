"""One close round publishes only its final reviewed commit."""
import stat
from pathlib import Path

import pytest

from test_close import body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client

STORY = "FIX-CLOSE-PUSHES-ONCE"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_publishes_once_after_saving_review(env, previous):
    client(env, previous)
    item, where = env.start_fix()
    updates = env.tmp / "published-heads"
    hook = Path(env.repo.git("remote", "get-url", "origin")) / "hooks" / "post-receive"
    hook.write_text(f'#!/bin/sh\ncat >> "{updates.as_posix()}"\n', encoding="utf-8")
    hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

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
