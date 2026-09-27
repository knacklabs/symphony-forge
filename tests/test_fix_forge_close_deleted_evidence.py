"""A dismissal can cite the base version of a file deleted by the branch."""

import pytest

from test_close import blocked, body, env, finding  # noqa: F401 (env is the fixture)

STORY = "FIX-FORGE-CLOSE-CAN-T-DISMISS-A-FINDING-ABOU"


@pytest.mark.parametrize(("change", "path", "line", "accepted"), [
    ("deleted", "secret.txt", 2, True),
    ("present", "app.py", 1, True),
    ("deleted", "secret.txt", 3, False),
    ("shortened", "secret.txt", 2, False),
    ("deleted", "café.txt", 2, True),
])
def test_1_close_uses_base_lines_only_for_deleted_files(env, change, path, line, accepted):
    base_path = path if path != "app.py" else "secret.txt"
    env.commit(env.repo.path, base_path, "old password\nremoved by migration\n")
    env.repo.git("push", "-q", "origin", "main")
    item, where = env.start_fix()
    if change == "deleted":
        (where / path).unlink()
        env.repo.git("add", "-u", cwd=where)
        env.repo.git("commit", "-q", "-m", "Remove old secret", cwd=where)
    elif change == "shortened":
        env.commit(where, path, "old password\n", "Remove old line")
    env.reviews(blocked(finding("P1", "Old password remains", file=path, line=1)))
    first = env.close(item)
    assert first.returncode == 1, first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)

    cited = f"{path}:{line} the branch removes the old password"
    second = env.close(item, "--dismiss", "1", "--because", cited)
    if not accepted:
        assert second.returncode == 1
        if change == "deleted":
            assert (f"{path}:{line} is not a line of the base commit, so it can't prove "
                    "a finding wrong.") in second.stderr
        else:
            assert (f"{path}:{line} is not a line of the reviewed commit, so it can't prove "
                    "a finding wrong.") in second.stderr
        assert not env.gh_calls("pr", "edit")
        return

    assert second.returncode == 0, second.stderr
    review_block = body(env.gh_calls("pr", "edit")[-1])
    assert f"dismissed because {cited}" in review_block
    if change == "deleted":
        assert "evidence from the base" in review_block
    else:
        assert "evidence from the base" not in review_block
