"""Real close, replay and PR check commands retain a reusable review's validity."""

import pytest

from test_close import env  # noqa: F401
from test_stacked_fixes_count_only_their_own_changes import configured, land_on_default, started

STORY = "review-after-replay"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_reused_review_passes_pr_check_after_replay(env, previous):
    repo = configured(env, previous)
    fix, where = started(repo, "Repair a greeting")
    env.commit(where, "src/greeting.py", "GREETING = 'Hello'\n")
    first = env.close(fix)
    assert first.returncode == 0, first.stdout + first.stderr
    old_head = repo.git("rev-parse", "HEAD", cwd=where)
    land_on_default(repo)
    # Replay the reviewed commits with an unchanged product diff. A parent's squash merge
    # changes the product diff and correctly requires another review, so it is not this case.
    repo.git("rebase", "origin/main", cwd=where)
    repo.git("push", "--force-with-lease", "origin", f"fix/{fix}", cwd=where)

    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 1
    head = repo.git("rev-parse", "HEAD", cwd=where)
    assert head != old_head
    checked = repo.forge("hook", "pr-check", "--base", repo.git("rev-parse", "origin/main"),
                         "--head", head, "--branch", f"fix/{fix}")
    assert checked.returncode == 0, checked.stdout + checked.stderr
    again = env.close(fix)
    assert again.returncode == 0, again.stdout + again.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == head
