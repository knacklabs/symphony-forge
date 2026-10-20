"""Only a recorded choice releases an owner stop, even beside a clean review after a merge."""
import json

import pytest

from test_close import CLEAN, STORY_DOC, env  # noqa: F401
from test_close_keeps_reviews_for_unchanged_branch_diffs import client
from test_close_waits_for_review_loop_choice import stopped
from test_hotspot_stop import saved
from test_land import land  # noqa: F401
from test_stuck_worker_asks import _rounds
from test_story import worktree

STORY = "stop-waits-for-owner"


@pytest.mark.parametrize("previous,kind,clean", [
    (False, "loop", False), (False, "loop", True), (True, "loop", True),
    (False, "stuck", True), (False, "size", True),
], ids=["new-loop", "new-clean-loop", "adopted-clean-loop", "new-stuck", "new-size"])
def test_1_owner_stop_survives_main_merge_until_the_choice_is_recorded(land, previous, kind, clean):
    env = land
    client(env, previous)
    if kind == "size":
        item, where = env.start_approved_task(STORY_DOC, changes={"app.py": "x = 1\n" * 401})
        held = env.close(item)
        assert held.returncode == 1 and "over its limit" in held.stderr
    elif kind == "stuck":
        config = (env.repo.path / "forge.toml").read_text("utf-8")
        env.commit(env.repo.path, "forge.toml", config.replace('workers = "split"', 'workers = "claude"'))
        env.repo.git("push", "-q", "origin", "main")
        item = _rounds(env, "finding")
        held = env.repo.forge("work", item)
        assert held.returncode == 1 and "Ask the human" in held.stderr
        where = worktree(env.repo, f"task/{item.replace('/', '-')}")
    else:
        item, where = stopped(env)
        held = env.close(item)
    assert "--resolve" in held.stderr
    question = held.stderr

    # Another change lands on main, then the worker brings main into the stopped item.
    merged = env.commit(env.repo.path, "NEWS.md", "Other work landed\n")
    env.repo.git("push", "-q", "origin", "main")
    env.repo.git("merge", "-q", "--no-edit", "origin/main", cwd=where)
    env.repo.git("merge-base", "--is-ancestor", merged, "HEAD", cwd=where)
    if kind == "size":
        # Main or a repair can make the part fit; that does not answer the owner's question.
        env.commit(where, "app.py", "x = 1\n")
    elif clean:
        # Earlier clients can leave a later clean result beside an unanswered stop.
        # Reproduce that persisted input; the real close command must retain the question.
        state = saved(where, item)
        state["review"].update(status="clean", findings=[], dismissals=[])
        record = (f".factory/stories/SHOP/tasks/{item.split('/')[-1]}.json" if "/" in item
                  else f".factory/fixes/{item}.json")
        env.commit(where, record, json.dumps(state), "Later clean review")
    env.reviews(CLEAN)
    before = len(env.review_calls())
    for _ in range(2):
        waiting = env.close(item)
        assert waiting.returncode == 1, waiting.stdout + waiting.stderr
        assert "Ask the human" in waiting.stderr and "--resolve" in waiting.stderr
        if kind != "loop":
            assert waiting.stderr == question
        assert len(env.review_calls()) == before
    reason = "The owner chooses one more focused round"
    chosen = env.close(item, "--resolve", "narrow" if kind == "loop" else "same", "--reason", reason)
    assert chosen.returncode == 0, chosen.stdout + chosen.stderr
    assert "Recorded the human's choice" in chosen.stdout
    assert saved(where, item)["stop"]["reason"] == reason
