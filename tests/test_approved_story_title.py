"""Approval names the current plan after a re-plan, on new and upgraded clients."""
import pytest

from test_approval_pin_notice import _waiting
from test_story import DOC, claude_plan, hook

STORY = "approval-commit-title"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-on-v1.2.2"])
def test_1_approval_commit_names_the_title_in_the_approved_story_doc(
        repo, gh, tmp_path, claude_payload, adopted):
    shop = _waiting(repo, gh, tmp_path, adopted)
    title = "Shoppers can restore a saved basket"
    replanned = DOC.replace("# Shoppers can save a basket", f"# {title}").replace(
        "save a basket", "restore a saved basket")
    (shop / "plans" / "SHOP.md").write_text(replanned, encoding="utf-8")
    read = repo.forge("read", "SHOP", cwd=shop)
    assert read.returncode == 0, read.stdout + read.stderr

    recorded = hook(repo, claude_plan(claude_payload, replanned, cwd=shop))
    assert recorded.returncode == 0, recorded.stdout + recorded.stderr
    assert repo.git("log", "-1", "--format=%s", "story/SHOP") == f"Approve the plan: {title}"
    assert f"Recorded the approval of {title}." in recorded.stdout
