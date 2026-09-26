"""The review prompt: a Not done finding blocks the merge only when this branch can meet it.

Each test is named test_<n>_<rule> after the Done-when item of STORY it proves.
"""
from __future__ import annotations

from pathlib import Path

STORY = "FIX-REVIEW-P1"
REVIEW = Path(__file__).resolve().parents[1] / "src" / "forge" / "templates" / "review.md"


def test_1_not_done_is_p1_only_when_the_branch_can_meet_it():
    text = " ".join(REVIEW.read_text(encoding="utf-8").split())
    assert "A `Not done` finding is P1 only when this branch can meet it" in text
    assert ("work that needs another task's code not yet on the default branch is a P2 "
            "`Later:` finding naming that task") in text
    assert ("an edge case the Done-when doesn't ask for, where the item's purpose is already "
            "met, is a P2") in text
    # Unchanged: a missing test and a missing functional check stay P1.
    assert "as a P1 finding titled `Not done: <the test>`" in text
    assert "P1 finding titled `Not done: functional check`" in text
