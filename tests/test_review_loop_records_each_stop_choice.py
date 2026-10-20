"""Each new P0 review stop needs its own owner decision.

An old choice must not bypass a later stop or prevent its new decision.
Real close, next and board commands guard the choice lifecycle; only the
external reviewer and GitHub are fake.
"""
import pytest

from test_close import blocked, env, finding  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_item_time_history import row

STORY = "second-stop-choice"


@pytest.mark.parametrize("previous,first,second", [
    (False, "more", "split"),
    (False, "accept", "accept"),
    (True, "split", "more"),
])
@pytest.mark.timeout(600)
def test_1_each_new_stop_waits_for_and_records_its_own_choice(
        env, tmp_path, previous, first, second):
    item, where = client_item(env, tmp_path, previous)
    number = 0
    for cycle, choice in enumerate((first, second)):
        # A fix stops on its first P0; each later new P0 needs a fresh choice too.
        number += 1
        env.commit(where, "app.py", f"print('round {number}')\n")
        env.reviews(blocked({**finding("P0", f"New defect {number}", "app.py"),
                             "body": "Gain 3, Work 2, Harm 5\nNormal saves lose work."}))
        result = env.close(item)
        assert result.returncode == 1, result.stdout + result.stderr
        assert len(env.review_calls()) == number
        assert "One more round, split or accept?" in result.stderr
        if cycle:
            assert row(env.repo, item)["status"] == "Needs your decision"
            next_step = env.repo.forge("next")
            assert next_step.returncode == 0, next_step.stderr
            assert f"forge close {item} --resolve <more|split|accept>" in next_step.stdout
            for command in ("close", "land"):
                waiting = env.repo.forge(command, item)
                assert waiting.returncode == (3 if command == "land" else 1), waiting.stdout + waiting.stderr
                assert "One more round, split or accept?" in waiting.stderr
                assert len(env.review_calls()) == number
        reason = f"The owner chose {choice} for stop {cycle + 1}"
        chosen = env.close(item, "--resolve", choice, "--reason", reason)
        assert chosen.returncode == 0, chosen.stdout + chosen.stderr
        assert "Recorded the human's choice" in chosen.stdout
        if cycle:
            assert row(env.repo, item)["status"] != "Needs your decision"
            duplicate = env.close(item, "--resolve", choice, "--reason", reason)
            assert duplicate.returncode == 1
            assert "Record the human's choice only on a stopped review loop" in duplicate.stderr
