"""Fixes use the configured review limit before they ask the owner.

Test audit: protects the close command's owner stop after two blocked reviews.
The regression is the fixed one-round limit for fixes. Existing configurable-limit
coverage does not exercise a second fix review or a clean review before a repair.
Only the external review service is faked; no production test seam is needed.
"""
import subprocess

import pytest

from test_close import CLEAN, blocked, body, env  # noqa: F401
from test_two_round_limit import client, note

STORY = "fix-review-rounds"


@pytest.mark.parametrize("clean_before_conflict", [False, True], ids=["blocked-first", "clean-then-conflict"])
def test_1_fix_reaches_second_blocked_review_before_owner_choice(env, clean_before_conflict):
    client(env, adopted=False)
    finding = note("P1", "The readme loses its greeting")
    env.reviews(blocked(finding))
    item, where = env.start_fix()
    if clean_before_conflict:
        env.reviews(CLEAN)
        clean = env.close(item)
        assert clean.returncode == 0, clean.stdout + clean.stderr
        env.open_pr(body(env.gh_calls("pr", "create")[-1]))
        env.commit(env.repo.path, "app.py", "print('upstream greeting')\n")
        env.repo.git("push", "-q", "origin", "main")
        env.repo.git("fetch", "-q", "origin", cwd=where)
        merged = subprocess.run(["git", "merge", "--no-edit", "origin/main"], cwd=where,
                                capture_output=True, text=True)
        assert merged.returncode == 1, merged.stdout + merged.stderr
        assert "app.py" in merged.stdout
        env.commit(where, "app.py", "print('resolved greeting')\n", "Resolve the greeting conflict")
        env.reviews(blocked(finding))
    first = env.close(item)
    assert first.returncode == 1, first.stdout + first.stderr
    assert finding["title"] in first.stdout + first.stderr
    assert "One more round, split or accept?" not in first.stdout + first.stderr
    assert "The review left serious findings open" in first.stdout + first.stderr
    if not clean_before_conflict:
        env.open_pr(body(env.gh_calls("pr", "create")[-1]), draft=True)
    env.commit(where, "app.py", "print('a repair that still misses the greeting')\n")
    env.reviews(blocked(finding))
    second = env.close(item)
    assert second.returncode == 1, second.stdout + second.stderr
    total = 3 if clean_before_conflict else 2
    assert len(env.review_calls()) == total
    assert finding["title"] in second.stdout + second.stderr
    assert f"Review round {total} of tidy-readme reached the round limit with open findings" in second.stderr
    assert "One more round, split or accept?" in second.stderr
