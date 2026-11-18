"""Fixes use the configured review limit before they ask the owner.

Test audit: protects the close command's owner stop after two blocked reviews.
The regression is the fixed one-round limit for fixes. Existing configurable-limit
coverage assumes that old rule and does not exercise a second fix review.
Only the external review service is faked; no production test seam is needed.
"""
from test_close import blocked, body, env  # noqa: F401
from test_two_round_limit import client, note

STORY = "fix-review-rounds"


def test_1_fix_reaches_second_blocked_review_before_owner_choice(env):
    client(env, adopted=False)
    finding = note("P1", "The readme loses its greeting")
    env.reviews(blocked(finding))
    item, where = env.start_fix()
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert finding["title"] in first.stdout + first.stderr
    assert "One more round, split or accept?" not in first.stdout + first.stderr
    assert "The review left serious findings open" in first.stdout + first.stderr
    env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    env.commit(where, "app.py", "print('a repair that still misses the greeting')\n")
    env.reviews(blocked(finding))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    assert len(env.review_calls()) == 2
    assert finding["title"] in second.stdout + second.stderr
    assert "Review round 2 of tidy-readme reached the round limit with open findings" in second.stderr
    assert "One more round, split or accept?" in second.stderr
