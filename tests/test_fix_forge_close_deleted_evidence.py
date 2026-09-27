"""A dismissal can cite the base version of a file deleted by the branch."""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401 (env is the fixture)

STORY = "FIX-FORGE-CLOSE-CAN-T-DISMISS-A-FINDING-ABOU"


@pytest.mark.parametrize(("deleted", "line", "accepted"), [
    (True, 2, True),
    (False, 1, True),
    (True, 3, False),
])
def test_1_close_uses_base_lines_only_for_deleted_files(env, deleted, line, accepted):
    env.commit(env.repo.path, "secret.txt", "old password\nremoved by migration\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    path = "secret.txt" if deleted else "app.py"
    if deleted:
        (where / path).unlink()
        env.repo.git("add", "-u", cwd=where)
        env.repo.git("commit", "-q", "-m", "Remove old secret", cwd=where)
    env.reviews(blocked(finding("P1", "Old password remains", file=path, line=1)))
    first = env.close(item)
    assert first.returncode == 1, first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)

    cited = f"{path}:{line} the branch removes the old password"
    second = env.close(item, "--dismiss", "1", "--because", cited)
    if not accepted:
        assert second.returncode == 1
        assert (f"{path}:{line} is not a line of the base commit, so it can't prove "
                "a finding wrong.") in second.stderr
        assert not env.gh_calls("pr", "edit")
        return

    assert second.returncode == 0, second.stderr
    review_block = body(env.gh_calls("pr", "edit")[-1])
    assert f"dismissed because {cited}" in review_block
    if deleted:
        assert "evidence from the base" in review_block
    else:
        assert "evidence from the base" not in review_block
