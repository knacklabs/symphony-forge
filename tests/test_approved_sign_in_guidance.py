"""Approved sign-in choices override password defaults in delivered guidance.

Test audit: init/sync output and the real close prompt are the public contracts.
A lost override in a shipped template recreates the bug; existing screen-order
tests and the package hash do not cover it. No production seam is needed.
Only the existing external GitHub and review-tool edges are fake.
"""

import pytest

from test_close import CLEAN, GREEN, env  # noqa: F401
from test_score_notes import _client_repo

STORY = "FIX-APPROVED-SIGN-IN"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_basic_screens_follow_approved_sign_in(env, tmp_path, previous):
    _client_repo(env, tmp_path, previous)
    # New-client init replaces API responses; restore the close fixture's check results.
    env.checks(GREEN)
    repo = env.repo
    item, where = env.start_fix(changes={
        "docs/decisions/sign-in.md":
            "# Approved sign-in\nUse company sign-in. Do not collect passwords.\n",
        "app.py": "print('company sign-in')\n",
    })
    synced = repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        skills = where / host / "skills"
        baseline = " ".join((skills / "app-baseline/SKILL.md").read_text("utf-8").split())
        guide = " ".join((skills / "forge/SKILL.md").read_text("utf-8").split())
        assert "default for email and password" in baseline
        for text in (baseline, guide):
            assert "approved sign-in answer, spec or decision" in text
            assert "which basic screens exist and what they hold" in text
            assert "do not build the password screens" in text
    repo.git("add", "-A", cwd=where)
    # Init and upgrade already sync current guidance, so another sync can change nothing.
    repo.git("commit", "--allow-empty", "-qm", "Refresh guidance", cwd=where)
    env.reviews(CLEAN)
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    prompt = " ".join(env.prompt().split())
    assert "approved sign-in answer" in prompt
    assert "docs/decisions" in prompt
    assert "specs" in prompt
    assert "Do not report a file that `forge sync` writes against the app" in prompt
    assert "new and changed work" in prompt
    assert "Do not ask an existing app to rebuild what it already has" in prompt
