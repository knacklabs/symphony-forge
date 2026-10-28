"""Land returns an actionable stop instead of keeping a coordinator alive."""
STORY = "land-exits-for-owner"

import sys
from pathlib import Path

import pytest

from conftest import GH_STUB, _install
from test_close import CLEAN, STORY_DOC, blocked, env, finding  # noqa: F401
from test_close_holds_after_three_blocked_reviews import client_item
from test_land import GH, URL, _red_checks, land  # noqa: F401
from test_tools_session_hold import Session


@pytest.mark.parametrize("previous", [False, True])
def test_1_owner_choice_exits_with_findings_and_checks_then_resumes(env, tmp_path, previous):
    item, where = client_item(env, tmp_path, previous, part=True)
    if not previous:
        # Init's prototype merges automatically: reuse land's GitHub edge fake for that final step.
        remote = Path(env.repo.git("remote", "get-url", "origin")).as_posix()
        _install(env.repo.bin, "gh", GH.format(python=sys.executable, remote=remote, url=URL)
                 + GH_STUB.format(python=sys.executable).split("\n", 1)[1])
    for host in (".codex", ".claude"):
        guide = " ".join((where / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "exits with status 3 (needs a choice)" in guide
        assert "Then run `forge land <item>` again." in guide
    for number in (1, 2):
        env.commit(where, "app.py", f"print({number})\n")
        # A P1 at the bar stops for the owner at round two.
        defect = finding("P1", f"Saving loses the greeting, case {number}")
        defect["body"] = "Gain 4, Work 1, Harm 2\nReturning readers lose their greeting."
        env.reviews(blocked(defect))
        assert env.close(item).returncode == 1
    _red_checks(env)
    # The review stop returns the question without starting another round.
    stopped = env.repo.forge("land", item, timeout=40)
    assert stopped.returncode == 3, stopped.stdout + stopped.stderr
    output = stopped.stdout + stopped.stderr
    assert "One more round, split or accept?" in output
    assert "Returning readers lose their greeting" in output
    assert "AssertionError: no greeting in README" in output
    assert f"forge close {item} --resolve" in output
    assert f"then forge land {item}" in output
    assert len(env.review_calls()) == 2
    env.gh.respond("pr", "checks", stdout="[]")
    env.gh.respond("pr", "view", "task/SHOP-T1", "--json", "url",
                   stdout='{"url": "https://github.com/acme/shop/pull/7"}')
    resolved = env.close(item, "--resolve", "accept", "--reason", "The owner accepts the greeting limit")
    assert resolved.returncode == 0, resolved.stdout + resolved.stderr
    resumed = env.repo.forge("land", item)
    assert resumed.returncode == 0, resumed.stdout + resumed.stderr
    assert len(env.review_calls()) == 2


def test_2_round_handoffs_show_findings_and_check_logs(land, monkeypatch):
    item, _ = land.start_approved_task(STORY_DOC)
    land.reviews(blocked(finding("P1", "Saving loses the greeting")), CLEAN)
    _red_checks(land)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    host = Session(land.repo, land.tmp / "host", "claude-session")
    try:
        done = host.forge("land", item)
        assert done.returncode == 0, done.stdout + done.stderr
        # The worker brief is in a file; the console must carry the evidence itself.
        assert "Saving loses the greeting" in done.stdout
        assert "AssertionError: no greeting in README" in done.stdout
        assert "forge handback" in done.stdout
    finally:
        host.close()
