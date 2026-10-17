"""Land returns an actionable stop instead of keeping a coordinator alive."""
STORY = "land-exits-for-owner"

import pytest

from test_close import CLEAN, blocked, env, finding  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_land import ITEM, _fix, _red_checks, land  # noqa: F401
from test_tools_session_hold import Session


@pytest.mark.parametrize("previous,harm", [(False, 1), (True, 3)])
def test_1_owner_choice_exits_with_findings_and_checks_then_resumes(env, tmp_path, previous, harm):
    item, where = client_item(env, tmp_path, previous)
    for host in (".codex", ".claude"):
        guide = " ".join((where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "exits with status 3 (needs a choice)" in guide
        assert "Then run `forge land <item>` again." in guide
    for number in (1, 2, 3):
        env.commit(where, "app.py", f"print({number})\n")
        if number == 3:
            env.commit(where, "README.md", "The owner requires a greeting on every page.\n")
        defect = finding("P1", f"Saving loses the greeting, case {number}")
        defect["body"] = f"Gain 4, Work 2, Harm {harm}\nReturning readers lose their greeting."
        env.reviews(blocked(defect))
        assert env.close(item).returncode == 1
    _red_checks(env)
    # The old contract waited indefinitely, including when high harm prevented a default.
    stopped = env.repo.forge("land", item, timeout=40)
    assert stopped.returncode == 3, stopped.stdout + stopped.stderr
    output = stopped.stdout + stopped.stderr
    assert "Accept, narrow or split?" in output
    assert "Returning readers lose their greeting" in output
    assert "AssertionError: no greeting in README" in output
    assert f"forge close {item} --resolve" in output
    assert f"then forge land {item}" in output
    assert len(env.review_calls()) == 3
    env.gh.respond("pr", "checks", stdout="[]")
    resolved = env.close(item, "--resolve", "accept", "--reason", "The owner accepts the greeting limit")
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    resumed = env.repo.forge("land", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(env.review_calls()) == 3


def test_2_round_handoffs_show_findings_and_check_logs(land, monkeypatch):
    _fix(land, "working", worked=True)
    land.reviews(blocked(finding("P1", "Saving loses the greeting")), CLEAN)
    _red_checks(land)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    host = Session(land.repo, land.tmp / "host", "claude-session")
    try:
        done = host.forge("land", ITEM)
        assert done.returncode == 0, done.stdout + done.stderr
        # The worker brief is in a file; the console must carry the evidence itself.
        assert "Saving loses the greeting" in done.stdout
        assert "AssertionError: no greeting in README" in done.stdout
        assert "forge handback" in done.stdout
    finally:
        host.close()
