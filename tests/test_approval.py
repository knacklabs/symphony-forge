"""Approval capture on both hosts, and the client sign-off gate (spec criteria 14 and 32)."""
from __future__ import annotations

import re

from test_story import DOC, claude_plan, codex_question, hook, ready, setup


def _digest(repo):
    """The Codex question id `forge next` gives for the one story waiting for approval."""
    return re.search(r"approve_plan_([0-9a-f]{64})", repo.forge("next").stdout)[1]


def test_14_approval_capture(repo, claude_payload, codex_payload):
    setup(repo, keys=("SHOP", "WISH", "GIFT", "CARD"))
    ready(repo, "SHOP")
    ready(repo, "WISH", DOC.replace("save a basket", "keep a wish list"))

    # Claude Code: a successful ExitPlanMode showing the doc records the approval, and commits the
    # doc, its read notes and its state on the story branch.
    claude_approval = claude_plan(claude_payload, DOC)
    recorded = hook(repo, claude_approval)
    assert recorded.returncode == 0, recorded.stderr
    assert "Recorded the approval" in recorded.stdout
    committed = repo.git("show", "--name-only", "--format=", "story/SHOP").splitlines()
    assert {"plans/SHOP.md", "plans/SHOP.read.md"} <= set(committed)
    assert any(path.startswith(".factory/") for path in committed)
    shown = repo.forge("next").stdout
    assert "Next: forge task start SHOP/SAVE" in shown and "SHOP/SHOW" not in shown

    # Codex: a completed request_user_input that follows the contract records it the same way.
    recorded = hook(repo, codex_question(codex_payload, _digest(repo)))
    assert recorded.returncode == 0, recorded.stderr
    assert "Next: forge task start WISH/SAVE" in repo.forge("next").stdout

    # Nothing is recorded, and forge next says why, for each of these.
    shared = DOC.replace("save a basket", "send a gift")
    gift, card = ready(repo, "GIFT", shared), ready(repo, "CARD", shared)
    heads = [repo.git("rev-parse", "story/GIFT"), repo.git("rev-parse", "story/CARD")]
    digest = _digest(repo)

    def refused(payload, problem):
        answer = hook(repo, payload)
        assert answer.returncode == 1 and answer.stderr.startswith(problem + "\nNext: ")
        assert problem.rstrip(".") in repo.forge("next").stdout
        assert [repo.git("rev-parse", "story/GIFT"), repo.git("rev-parse", "story/CARD")] == heads

    refused(codex_question(codex_payload, digest),
            "The approved plan matches 2 story docs, so nothing was recorded.")
    (card / "plans" / "CARD.md").write_text(shared.replace("2. The basket", "2. The card"),
                                            encoding="utf-8")
    assert repo.forge("read", "CARD", "--amended").returncode == 0
    cancelled = codex_question(codex_payload, digest)
    cancelled["tool_response"]["status"] = "cancelled"
    refused(cancelled, "The approval question was cancelled or failed, so nothing was recorded.")
    refused(codex_question(codex_payload, digest, answer="Request changes"),
            'The answer was "Request changes", not "Approve plan", so nothing was recorded.')
    no_match = ("The approved plan matches no story doc waiting for approval; it may have changed "
                "since it was shown.")
    refused(codex_question(codex_payload, "0" * 64), no_match)  # a stale digest
    refused(claude_plan(claude_payload, "# A plan\n\nIt is no story doc.\n"), no_match)
    refused(codex_payload("PostToolUse", "ExitPlanMode", {"plan": shared}, {"status": "success"}),
            "ExitPlanMode is not Codex's approval tool, so nothing was recorded.")
    refused(claude_approval, "This approval was already recorded once; a replay records nothing.")

    recorded = hook(repo, codex_question(codex_payload, digest, cwd=gift))
    assert recorded.returncode == 0, recorded.stderr
    assert repo.git("rev-parse", "story/GIFT") != heads[0]
    assert "the last answer was not recorded" not in repo.forge("next").stdout


def test_32_client_signoff(repo, claude_payload):
    setup(repo, kind="client", keys=("SHOP", "OWN"))
    shop = ready(repo, "SHOP")
    head = repo.git("rev-parse", "story/SHOP")
    approval = claude_plan(claude_payload, DOC)

    refused = hook(repo, approval)
    assert refused.returncode == 1
    assert refused.stderr == (
        "This client's sign-off isn't recorded yet, so the approval was not recorded.\n"
        'Next: forge decision new client-signoff, then forge decision accept client-signoff '
        '--by "<client name>"\n')
    shown = repo.forge("next").stdout
    assert "can't be approved until the client's sign-off is recorded" in shown
    assert "forge decision accept client-signoff" in shown
    assert repo.git("rev-parse", "story/SHOP") == head

    # Forge's own repo needs no sign-off.
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n')
    repo.git("commit", "-q", "-am", "This is Forge's own repo")
    own = DOC.replace("save a basket", "own a basket")
    ready(repo, "OWN", own)
    assert hook(repo, claude_plan(claude_payload, own)).returncode == 0

    # Once the client's sign-off decision is accepted, the same approval records.
    # ponytail: RECORDS' `forge decision accept` isn't in this branch; this is the file it writes.
    repo.write("docs/decisions/0001-client-signoff.md",
               '---\nstatus: accepted\nconfirmed_by: "A Client"\n---\n\n# The client signed off\n')
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "The client signed off")
    repo.git("push", "-q", "origin", "main")  # as when the decision's fix merges
    assert not (shop / "docs" / "decisions").exists()  # so it is found on the default branch
    recorded = hook(repo, approval)
    assert recorded.returncode == 0, recorded.stderr
    assert "Next: forge task start SHOP/SAVE" in repo.forge("next").stdout
