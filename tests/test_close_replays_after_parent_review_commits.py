"""Close replays a stacked part's own work, not the parent's later edits that it picked up."""

import pytest

from test_close import env  # noqa: F401
from test_close_replays_followup_after_squash_merge import remote_head, stacked
from test_stacked_fixes_count_only_their_own_changes import land_on_default

pytestmark = pytest.mark.platform

STORY = "stacked-replay-parent-review"


@pytest.mark.parametrize("previous", [False, True], ids=["new", "previously-adopted"])
def test_1_close_skips_parent_review_commits_the_part_picked_up(env, previous):
    repo, parent, _, fix, where, own = stacked(env, previous)
    parent_folder = where.parent / f"{where.name.rsplit('-fix-', 1)[0]}-fix-{parent}"
    # The parent edits one file twice after the part started, and the part merges both edits.
    for text in ("REVIEW = 1\n", "REVIEW = 2\n"):
        env.commit(parent_folder, "src/review_note.py", text, "Review of the parent")
    repo.git("merge", "-q", "--no-edit", f"fix/{parent}", cwd=where)
    repo.git("push", "-q", "origin", f"fix/{fix}", cwd=where)
    land_on_default(repo, parent)
    land_on_default(repo, path="src/new_default.py")

    closed = env.close(fix)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "conflicts in" not in closed.stderr
    assert (where / "src/review_note.py").read_text("utf-8") == "REVIEW = 2\n"
    assert (where / "src/shared.py").read_text("utf-8") == own
    assert repo.git("diff", "--name-only", "origin/main", "HEAD", "--", "src", cwd=where) == "src/shared.py"
    assert remote_head(repo, fix) == repo.git("rev-parse", "HEAD", cwd=where)
