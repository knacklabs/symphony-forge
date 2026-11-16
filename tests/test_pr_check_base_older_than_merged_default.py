STORY = "FIX-REVIEW-CHECK-RACE"
# The review check reads the clean review against the newest default-branch commit the head merged,
# not the event's older base.

from test_close import env  # noqa: F401


def test_3_clean_review_passes_when_the_event_base_is_older_than_the_merged_default(env):
    item, where = env.start_fix()
    old = env.repo.git("rev-parse", "origin/main", cwd=where)
    env.commit(where, "app.py", "print('hello again')\n", "Repair greeting\n\nFunctional check: Ran it.")
    env.commit(env.repo.path, "other.py", "OTHER = 1\n")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    head = env.repo.git("rev-parse", f"refs/remotes/origin/fix/{item}", cwd=where)
    checked = env.repo.forge("hook", "pr-check", "--base", old, "--head", head,
                             "--branch", f"fix/{item}", cwd=where)
    assert checked.returncode == 0, checked.stdout + checked.stderr
