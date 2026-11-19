"""Close publishes a clean final change despite an intermediate replay conflict."""

from test_close import env  # noqa: F401
from test_close_replays_after_parent_review_commits import (
    OWN_WORK, parent_merged_after_part_picked_up_its_review_commits,
)

STORY = "squash-replay-on-conflict"


def test_1_close_squashes_only_intermediate_conflicts(env):
    # Audit: preserve the final change and evidence through the real close command.
    # Existing replay cases have no conflicting intermediate edit with a clean tip.
    # Only remote services are faked; no production testing seam is needed.
    repo, part = parent_merged_after_part_picked_up_its_review_commits(env, False, "one-pickup")
    env.commit(part, "app.py", "A_VALUE = 2\n", "Try an intermediate value")
    env.commit(part, "app.py", "A_VALUE = 3\n", OWN_WORK)
    writer = repo.path.parent / "default-writer"
    env.commit(writer, "app.py", "A_VALUE = 3\n", "Change the same value on main")
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    default = repo.git("rev-parse", "origin/main")

    closed = env.close("STACK/B")

    assert closed.returncode == 0, closed.stdout + closed.stderr
    repo.git("merge-base", "--is-ancestor", default, "HEAD", cwd=part)
    assert (part / "app.py").read_text("utf-8") == "A_VALUE = 3\n"
    assert (part / "use.py").read_text("utf-8") == "B_VALUE = 1\n"
    assert repo.git("rev-list", "--count", f"{default}..HEAD", "--", "app.py", "use.py",
                    cwd=part) == "1"
    messages = repo.git("log", "--format=%B", f"{default}..HEAD", cwd=part)
    for paragraph in ("Before coding:", "Functional check: ran the part", "Proof list:",
                      "the part's own value is read"):
        assert paragraph in messages
    assert repo.git("ls-remote", "--heads", "origin", "task/STACK-B").split()[0] == repo.git(
        "rev-parse", "HEAD", cwd=part)
    assert repo.git("status", "--porcelain", cwd=part) == ""
