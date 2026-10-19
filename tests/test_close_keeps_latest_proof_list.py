"""Close delivers the newest proof list after a coordinator merges main into a fix."""

import pytest

from test_close import body, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_reviews_receive_done_when_proof import checked

STORY = "proof-list-after-merge"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade"])
def test_1_review_reads_newest_proof_list_after_main_merge(env, previous):
    # Audit: real close owns proof delivery; GitHub and Autoreview alone are faked.
    # Existing delivery coverage required the latest commit to repeat the list.
    client(env, previous)
    item, where = env.start_fix()
    old = "Proof list:\n- Greeting: the first greeting check"
    newest = "Proof list:\n- Greeting: the complete greeting check"
    env.commit(where, "app.py", "print('first greeting')\n", "First greeting\n\n" + old)
    env.commit(where, "app.py", "print('complete greeting')\n", "Complete greeting\n\n" + newest)
    env.commit(env.repo.path, "NEWS.md", "Other work landed\n",
               "Land other work\n\nProof list:\n- Unrelated main proof")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert checked(newest) in env.prompt()

    # The merge is already excluded. A later non-bookkeeping commit without a
    # label stopped the old search and hid the worker's newest proof list.
    env.open_pr(body(env.gh_calls("pr", "create")[-1]))
    env.commit(where, "app.py", "print('complete greeting again')\n", "Retain the greeting")
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert len(env.review_calls()) == 2
    assert checked(newest) in env.prompt()
    assert checked(newest) in body(env.gh_calls("pr", "edit")[-1])
    assert "the first greeting check" not in env.prompt()
    assert "Unrelated main proof" not in env.prompt()
