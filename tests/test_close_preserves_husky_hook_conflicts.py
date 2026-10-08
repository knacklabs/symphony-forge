"""Close leaves conflicts in user-owned Husky hooks for the worker to resolve."""
import pytest

from test_close import env  # noqa: F401

STORY = "FIX-HUSKY-HOOKS"


@pytest.mark.parametrize("hook", ["pre-commit", "pre-push"])
def test_close_refuses_user_husky_hook_conflicts_without_discarding_either_side(env, hook):
    repo = env.repo
    repo.git("config", "core.hooksPath", ".husky/_")
    path = f".husky/{hook}"
    env.commit(repo.path, path, "echo original check\n")
    repo.git("push", "-q", "origin", "main")
    worker = "echo worker check\n"
    default = "echo default check\n"
    item, where = env.start_fix({path: worker})
    moved = env.commit(repo.path, path, default)
    repo.git("push", "-q", "origin", "main")
    before = repo.git("rev-parse", "HEAD", cwd=where)

    closed = env.close(item)

    assert closed.returncode == 1, closed.stdout + closed.stderr
    assert f"Merging main into fix/tidy-readme conflicts in {path}." in closed.stderr
    assert repo.git("rev-parse", "HEAD", cwd=where) == before
    assert (where / path).read_text("utf-8") == worker
    assert repo.git("show", f"origin/main:{path}", cwd=where) == default.rstrip("\n")
    assert repo.git("rev-parse", "origin/main", cwd=where) == moved
    assert repo.git("status", "--porcelain", cwd=where) == ""
    assert not env.review_calls()
