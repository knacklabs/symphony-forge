"""The review prompt separates speculative test advice from present proof gaps.

Test audit: this pins the instructions delivered by real close. Removing the advice
boundary can waste a review round; a present proof gap must still block. Existing
prompt tests cover other review rules. No production seam or model answer is faked.
"""
from test_close import env  # noqa: F401

STORY = "FIX-TEST-FINDINGS-ADVISE"


def test_1_review_keeps_future_test_rewrites_as_advice(env):
    item, _ = env.start_fix()
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert "A Test or Gate finding based only on a future change to a test fake or GitHub call order is advice" in prompt
    assert "a fake that matches exact request text" in prompt
    assert "selecting a GitHub call by position or counting unrelated calls" in prompt
    assert "Report it as P2 with Gain 2, Work 1, Harm 1; it does not block close" in prompt
    assert "A real gap where today's code can do the wrong thing and the test still passes keeps its normal blocking score" in prompt
