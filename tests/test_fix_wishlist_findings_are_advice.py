"""Findings beyond what the item promises are advice: they never block, and close lists them apart."""
from __future__ import annotations

from test_close import blocked, env, finding  # noqa: F401  (env is a fixture)

STORY = "most-extra-review-rounds-come-from-findi"


def test_1_review_blocks_only_on_real_gaps_and_wishlists_are_p2(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    prompt = " ".join(env.prompt().split())
    for blocker in ("a defect that would ship", "a security, data-loss or accessibility gap",
                    "an unmet Done-when item", "a missing test for a Done-when item's own behaviour"):
        assert blocker in prompt
    assert ("Extra edge-case tests, platform or hardening suggestions beyond what the item "
            "promises are P2") in prompt
    assert "never block the merge or start another round" in prompt
    # The rules against dropping validation, security, data-loss protection and accessibility stay.
    assert ("validation, authorization, secrets handling, data-loss protection and accessibility "
            "are never \"simpler\": a missing one is its own P1 finding") in prompt


def test_2_close_lists_non_blocking_findings_under_their_own_heading(env):
    item, _ = env.start_fix()
    env.reviews(blocked(finding("P1", "Not done: The readme opens with a greeting"),
                        finding("P2", "Add a test for an empty readme")))
    first = env.close(item)
    assert first.returncode == 1
    blocking, advice = first.stdout.split("Advice that does not block the merge:\n", 1)
    assert "P1 Not done: The readme opens with a greeting" in blocking
    assert "P1" not in advice
    assert "2. P2 Add a test for an empty readme (app.py:1)" in advice

    # Advice alone never blocks: once the P1 is dismissed, close goes on and still lists it.
    second = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting is here")
    assert second.returncode == 0, second.stderr
    advice = second.stdout.split("Advice that does not block the merge:\n", 1)[1]
    assert "2. P2 Add a test for an empty readme (app.py:1)" in advice
    assert "Not done" not in advice
