"""Findings beyond what the item promises are advice: they never block, and close lists them apart."""
from __future__ import annotations

from test_close import blocked, env, finding  # noqa: F401  (env is a fixture)

import pytest

STORY = "most-extra-review-rounds-come-from-findi"


def test_1_review_blocks_only_on_real_gaps_and_wishlists_are_p2(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0
    prompt = " ".join(env.prompt().split())
    for blocker in ("Functional: a defect on a path people or agents normally hit",
                    "Security: a security gap", "Data loss: data lost, corrupted or exposed",
                    "Not done: an unmet owner-approved Done-when item",
                    "Test: a missing or hollow test for a Done-when item's own behaviour"):
        assert blocker in prompt
    assert "- hardening beyond what the item promises;" in prompt
    assert "never block the merge or start another round" in prompt
    # The rules against dropping validation, security, data-loss protection and accessibility stay.
    assert ("validation, authorization, secrets handling, data-loss protection and accessibility "
            "are never \"simpler\": a missing one is its own P1 finding") in prompt


@pytest.mark.platform
def test_2_close_lists_non_blocking_findings_under_their_own_heading(env):
    item, _ = env.start_task()
    env.reviews(blocked(finding("P1", "Not done: A shopper can save a basket."),
                        finding("P2", "Add a test for an empty readme")))
    first = env.close(item)
    assert first.returncode == 1
    blocking, advice = first.stdout.split("Advice that does not block the merge:\n", 1)
    assert "P1 Not done: A shopper can save a basket." in blocking
    assert "P1" not in advice
    assert "2. P2 Add a test for an empty readme (app.py:1)" in advice

    # A clean review labels its remaining advice as follow-ups and omits priority labels.
    second = env.close(item, "--dismiss", "1", "--because", "app.py:1 the greeting is here")
    assert second.returncode == 0, second.stderr
    advice = second.stdout.split(
        "Follow-ups that do not block the merge (recorded in the pull request):\n", 1)[1]
    assert "2. Add a test for an empty readme (app.py:1)" in advice
    assert "Not done" not in advice
