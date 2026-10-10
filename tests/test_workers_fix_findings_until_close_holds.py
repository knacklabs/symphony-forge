"""Workers wait for a review-loop choice only after close holds the loop."""
import pytest

from test_close import env  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_worker import calls, install_claude

STORY = "worker-no-idle-choice"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "previous-adoption-sync"])
def test_1_workers_fix_each_round_unless_close_has_stopped_the_review_loop(env, tmp_path, previous):
    item, where = client_item(env, tmp_path, previous)
    config = (where / "forge.toml").read_text("utf-8")
    env.commit(where, "forge.toml", config.replace('workers = "codex"',
                                                  'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"'))
    log = install_claude(env.repo)
    worked = env.repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    # The old unconditional wait made each finding look like a fresh choice.
    # This is a delivered prompt contract; the host stub only captures its input.
    assert ("Wait for a recorded choice only after close has stopped the review loop. "
            "Otherwise, fix the findings in this round, including new findings after a recorded "
            "narrow or split; do not ask for another choice unless close stops the loop again.") in brief
    assert "This rule applies in later rounds too." in brief
    resumed = env.repo.forge("work", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    call = calls(log)[-1]
    assert "--resume" in call["args"]
    assert "The earlier brief in this conversation still applies." in call["brief"]
