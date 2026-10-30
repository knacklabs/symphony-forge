"""A review's Later findings for another item keep their scores through close."""
import pytest

from test_close import GREEN, blocked, body, env  # noqa: F401 (env is a fixture)
from test_score_notes import _client_repo, _scored

STORY = "FIX-LATER-NOT-FLOORED"


@pytest.mark.parametrize("previous", [False, True], ids=["init", "earlier-adoption-upgrade-sync"])
def test_1_later_findings_for_another_item_do_not_trigger_floors(env, tmp_path, previous):
    # Existing floor coverage protects current-item defects. These notes explicitly defer
    # work to another item: neither a migration mention nor a Raise label must block this one.
    _client_repo(env, tmp_path, previous)
    env.checks(GREEN)  # init's GitHub setup replaces the fixture's earlier API responses.
    findings = [
        _scored("P2", "Later: SHOP/T2 moves old baskets",
                "Gain 3, Work 3, Harm 1\nRaise: Functional\nSHOP/T2 adds the migration."),
        _scored("P2", "Later: SHOP/T2 adds the basket migration",
                "Gain 3, Work 3, Harm 1\nRaise: Functional\nSHOP/T2 owns this work."),
        _scored("P2", "Later: SHOP/T2 guards basket access",
                "Gain 3, Work 3, Harm 1\nRaise: Security\nSHOP/T2 owns this work."),
        _scored("P2", "Later: SHOP/T2 preserves baskets",
                "Gain 3, Work 3, Harm 1\nRaise: Data loss\nSHOP/T2 owns this work."),
    ]
    env.reviews(blocked(*findings))
    item, _ = env.start_fix()

    closed = env.close(item)

    assert closed.returncode == 0, closed.stdout + closed.stderr
    published = body(env.gh_calls("pr", "edit")[-1])
    for finding in findings:
        assert f"{finding['title']} (app.py:1): Gain 3, Work 3, Harm 1" in published
    assert "(floor:" not in published
    assert env.gh_calls("pr", "ready") == [["pr", "ready", "7"]]
