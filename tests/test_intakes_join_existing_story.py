"""A second intake extends the same plan through the real handback command."""
import pytest

from test_start_sorts_ideas import (  # noqa: F401
    intake, land, env, _signed_off, _started, _plan, _offer, _back, _checkout,
)
from test_story import approved_constitution

STORY = "FIX-HANDBACK-EXISTING-STORY"


@pytest.mark.parametrize("checked_out", [True, False], ids=["worktree", "branch"])
def test_1_handback_adds_an_intake_to_an_existing_story(intake, checked_out):
    repo, top, *_ = intake
    _signed_off(intake)
    approved_constitution(repo, where=top)
    _started(intake, "Save baskets", _plan())
    checkout = _checkout(repo, top, "story/SAVE")
    original = (checkout / "plans/SAVE.md").read_text("utf-8")
    if not checked_out:
        repo.git("worktree", "remove", str(checkout), cwd=top)
    offered = _offer(intake, "Share saved baskets")
    reply = _plan().replace("Shoppers save their basket.", "Shoppers share a saved basket.").replace(
        "A shopper can save a basket.", "A shopper can share a saved basket.")
    joined = _back(intake, offered, reply)
    assert joined.returncode == 0, joined.stdout + joined.stderr
    assert "Added the idea to the story SAVE in " in joined.stdout
    assert "git worktree failed" not in joined.stdout + joined.stderr
    assert "forge doctor" not in joined.stdout + joined.stderr
    assert joined.stdout.splitlines()[-1].endswith("then forge read SAVE")
    checkout = _checkout(repo, top, "story/SAVE")
    updated = (checkout / "plans/SAVE.md").read_text("utf-8")
    assert "- Shoppers save their basket." in original
    for line in ("- Shoppers save their basket.", "- Shoppers share a saved basket.",
                 "1. **A shopper can save a basket.**", "2. **A shopper can share a saved basket.**"):
        assert line in updated
    assert repo.git("status", "--porcelain", cwd=checkout) == ""
