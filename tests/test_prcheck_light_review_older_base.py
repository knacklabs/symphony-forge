"""forge-pr-check keeps a clean light review when the check's event base is older."""
from __future__ import annotations

from test_close import env  # noqa: F401 (env is the shared fixture)


def test_1_docs_only_light_review_passes_with_older_event_base(env):
    item, where = env.start_fix({"README.md": "Hello\n"})
    old_base = env.repo.git("rev-parse", "HEAD")
    assert env.close(item).returncode == 0
    # The default branch gets code, and the fix branch merges it after the review.
    env.commit(env.repo.path, "app.py", "value = 1\n", "Unrelated code")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("fetch", "-q", "origin", cwd=where)
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    done = env.repo.forge("hook", "pr-check", "--base", old_base, "--branch", "fix/tidy-readme",
                          "--head", env.repo.git("rev-parse", "HEAD", cwd=where))
    assert done.returncode == 0, done.stderr
