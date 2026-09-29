"""Recording a story's approval pushes the story branch, so tasks started from it carry the approval."""
from __future__ import annotations

from test_story import DOC, claude_plan, hook, ready, setup

STORY = "recording-a-story-s-approval-doesn-t-pus"


def test_1_approving_a_story_pushes_its_branch_and_says_when_it_cannot(repo, claude_payload, tmp_path):
    setup(repo, keys=("SHOP", "WISH", "GIFT"))
    docs = {key: DOC.replace("save a basket", f"save a basket for {key}") for key in ("SHOP", "WISH", "GIFT")}
    for key, doc in docs.items():
        ready(repo, key, doc)

    def approve(key):
        recorded = hook(repo, claude_plan(claude_payload, docs[key]))
        assert recorded.returncode == 0, recorded.stderr
        assert "Recorded the approval" in recorded.stdout
        assert repo.git("log", "-1", "--format=%s", f"story/{key}").startswith("Approve the plan: ")
        return recorded.stdout + recorded.stderr

    def on_origin(key):
        return repo.git("ls-remote", "origin", f"refs/heads/story/{key}").split()[:1]

    # With a remote, the approval commit reaches origin.
    approve("SHOP")
    assert on_origin("SHOP") == [repo.git("rev-parse", "refs/heads/story/SHOP")]

    # A push the remote refuses is said in one line, and the approval stands.
    rejecting = tmp_path / "remote.git" / "hooks" / "pre-receive"
    rejecting.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
    rejecting.chmod(0o755)
    said = approve("WISH")
    assert ("Forge couldn't push story/WISH; run git push origin story/WISH so tasks see this "
            "approval.") in said
    assert on_origin("WISH") == []

    # Without a remote there is nothing to push, and nothing is said about it.
    repo.git("remote", "remove", "origin")
    assert "push" not in approve("GIFT")
