"""Close keeps branch history when a default merge avoids an intermediate replay conflict."""

import pytest

from test_close import env  # noqa: F401
from test_close_replays_followup_after_squash_merge import remote_head, stacked
from test_stacked_fixes_count_only_their_own_changes import land_on_default

STORY = "merge-before-replay"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_merges_clean_default_without_replaying_intermediate_commits(env, previous):
    repo, parent, _, fix, where, _ = stacked(env, previous)
    final = "FINAL = True\n" + "# stable\n" * 20
    original = env.commit(where, "src/shared.py", final)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    land_on_default(repo, parent)
    writer = repo.path.parent / "default-writer"
    env.commit(writer, "src/shared.py", final)
    repo.git("push", "-q", "origin", "main", cwd=writer)
    repo.git("fetch", "-q", "origin")
    default = repo.git("rev-parse", "origin/main")
    # Both tips agree, but replaying the earlier FOLLOWUP edit onto FINAL conflicts.
    # A behind PR requires close to merge, rather than leave a clean branch alone.
    env.gh.respond("pr", "list", "--head", stdout=
                   '[{"number":7,"state":"OPEN","body":"","isDraft":false,'
                   '"mergeStateStatus":"BEHIND"}]')

    closed = env.close(fix)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    repo.git("merge-base", "--is-ancestor", original, "HEAD", cwd=where)
    repo.git("merge-base", "--is-ancestor", default, "HEAD", cwd=where)
    assert (where / "src/shared.py").read_text("utf-8") == final
    assert remote_head(repo, fix) == repo.git("rev-parse", "HEAD", cwd=where)
    assert repo.git("status", "--porcelain", cwd=where) == ""
    assert "rebase" not in closed.stderr and "--force" not in closed.stderr
