"""A second intake extends the same plan through the real handback command.

Test audit: additions belong to their own sections and keep trailing Design
metadata valid. Matching through intervening headings breaks this contract.
The earlier fixture had adjacent sections and no Design line. Extend this
boundary owner with an established plan, without a production test seam.
"""
import re

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
    doc = checkout / "plans/SAVE.md"
    design = "Design: none (Small changes to the existing basket screen)"
    original = doc.read_text("utf-8").replace(
        "## Why\n", f"{design}\n\n## Background\n\nKeep the basket history.\n\n## Why\n"
    ).replace("## Done when\n", "## Evidence\n\nCustomers lose baskets.\n\n## Done when\n").replace(
        "## Risks\n", "## Delivery notes\n\n2. Keep existing basket links.\n\n## Risks\n"
    )
    doc.write_text(original, encoding="utf-8", newline="\n")
    repo.git("add", "plans/SAVE.md", cwd=checkout)
    repo.git("commit", "-q", "-m", "Expand the basket plan", cwd=checkout)
    if not checked_out:
        repo.git("worktree", "remove", str(checkout), cwd=top)
    offered = _offer(intake, "Share saved baskets")
    reply = _plan().replace("Shoppers save their basket.", "Shoppers share a saved basket.").replace(
        "A shopper can save a basket.", "A shopper can share a saved basket.").replace(
        "Shoppers lose baskets when they leave.", "People cannot share a basket.")
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
    sections = dict(block.split("\n", 1) for block in re.split(r"(?m)^## ", updated)[1:])
    assert "- Shoppers share a saved basket." in sections["What changes for you"]
    assert sections["What changes for you"].strip().splitlines()[-1] == design
    assert "Shoppers lose baskets when they leave." in sections["Why"]
    assert "People cannot share a basket." in sections["Why"]
    assert "2. **A shopper can share a saved basket.**" in sections["Done when"]
    for heading in ("Background", "Evidence", "Delivery notes", "Risks", "Tasks"):
        original_body = re.split(r"(?m)^## ", original.split(f"## {heading}\n", 1)[1])[0]
        assert sections[heading] == original_body
    assert repo.git("status", "--porcelain", cwd=checkout) == ""
