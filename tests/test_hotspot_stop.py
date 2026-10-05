STORY = "FORGE-SPOTTED-1"

import json
import pytest

from test_close import blocked, env, finding  # noqa: F401


def seed(env, path):
    env.repo.write(path, "pass\n")
    env.repo.git("add", "--", path)
    env.repo.git("commit", "-q", "-m", "Existing code")
    env.repo.git("push", "-q", "origin", "main")


def saved(where, item):
    path = (f".factory/stories/SHOP/tasks/{item.split('/')[-1]}.json" if "/" in item
            else f".factory/fixes/{item}.json")
    return json.loads((where / path).read_text())


def rounds(env, item, where, paths):
    for number, path in enumerate(paths, 1):
        env.reviews(blocked(finding("P1", f"Round {number} defect", path)))
        env.commit(where, "app.py", f"print({number})\n")
        result = env.close(item)
        assert result.returncode == 1, result.stdout + result.stderr
        if number < len(paths):
            assert "The review left serious findings open:" in result.stderr
    return result


def _other_blocked_reviews_keep_the_existing_refusal(env, paths, on_default):
    if on_default:
        for path in sorted(set(paths)):
            seed(env, path)
    item, where = env.start_fix()
    if not on_default:
        env.commit(where, paths[0], "pass\n")
    result = rounds(env, item, where, paths)
    assert "The review left serious findings open:" in result.stderr
    assert saved(where, item)["status"] == "fixing"
    assert "stop" not in saved(where, item)


def _carried_dismissal_cannot_stop_the_third_review(env):
    seed(env, "src/a.py")
    item, where = env.start_fix()
    defect = blocked(finding("P1", "Dismissed defect", "src/a.py"))
    env.reviews(defect)
    assert env.close(item).returncode == 1
    assert env.close(item, "--dismiss", "1", "--because", "src/a.py:1 Proven safe").returncode == 0
    for number in (2, 3):
        env.commit(where, "app.py", f"print({number})\n")
        env.reviews(defect)
        result = env.close(item)
        assert result.returncode == 0, result.stderr
    state = saved(where, item)
    assert len([step for step in state["steps"] if step["step"] == "review"]) == 3
    assert "stop" not in state


@pytest.mark.parametrize("case,details", [
    *[(_other_blocked_reviews_keep_the_existing_refusal, details) for details in (
        (["src/a.py", "src/b.py", "src/c.py"], True),
        (["src/a.py", "src/a.py"], True),
        (["src/branch.py"] * 3, False),
        (["src/$cache.py"] * 3, True))],
    (_carried_dismissal_cannot_stop_the_third_review, ()),
])
def test_5_other_reviews_keep_the_existing_refusal(env, case, details):
    case(env, *details)
