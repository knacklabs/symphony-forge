"""A task review follows its changed files and keeps justified dismissals across rounds."""

import pytest

from test_close import CLEAN, blocked, body, env, finding  # noqa: F401 (env is the fixture)

STORY = "FIX-MERGING-THE-DEFAULT-BRANCH-INTO-A-TASK-M"


def test_1_review_stays_current_when_close_merges_unrelated_default_change(env):
    item, _ = env.start_task()
    assert env.close(item).returncode == 0
    assert len(env.review_calls()) == 1

    env.commit(env.repo.path, "NEWS.md", "The shop opens.\n")
    env.repo.git("push", "-q", "origin", "main")
    again = env.close(item)

    assert again.returncode == 0, again.stderr
    assert len(env.review_calls()) == 1


@pytest.mark.parametrize("change", ["edit", "delete"])
def test_2_review_becomes_stale_when_a_branch_file_changes(env, change):
    item, where = env.start_task()
    assert env.close(item).returncode == 0

    if change == "edit":
        env.commit(where, "app.py", "print('saved twice')\n")
    else:
        (where / "app.py").unlink()
        env.repo.git("add", "-u", cwd=where)
        env.repo.git("commit", "-q", "-m", "Remove the save code", cwd=where)
    again = env.close(item)

    assert again.returncode == 0, again.stderr
    assert len(env.review_calls()) == 2


def test_3_close_carries_dismissal_to_same_file_and_title_in_later_review(env):
    item, where = env.start_task()
    title = "Saving loses the basket"
    reason = "app.py:1 the basket is saved here"
    env.reviews(blocked(finding("P1", title)),
                blocked(finding("P2", "Simpler: remove the cache"),
                        finding("P1", title, line=2)))
    first = env.close(item)
    assert first.returncode == 1
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)

    dismissed = env.close(item, "--dismiss", "1", "--because", reason)
    assert dismissed.returncode == 0, dismissed.stderr
    env.open_pr(body(env.gh_calls("pr", "edit")[-1]))

    env.commit(where, "app.py", "print('saved twice')\nprint('still saved')\n")
    again = env.close(item)

    assert again.returncode == 0, again.stderr
    assert len(env.review_calls()) == 2
    assert f"2. P1 {title} (app.py:2): dismissed because {reason}" in body(
        env.gh_calls("pr", "edit")[-1])
