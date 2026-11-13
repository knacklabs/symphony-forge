"""A background refresh keeps the screen: the shipped app-baseline skill says so.

Test audit: init/sync output is the public contract. A lost sentence in the template
recreates the bug; the package hash only pins bytes. No production seam is needed.
"""

import pytest

from test_close import GREEN, env  # noqa: F401
from test_score_notes import _client_repo

STORY = "FIX-BACKGROUND-REFRESH"


@pytest.mark.platform
@pytest.mark.parametrize("previous", [False, True], ids=["new", "earlier-adopted"])
def test_1_baseline_keeps_the_screen_on_a_background_refresh(env, tmp_path, previous):
    _client_repo(env, tmp_path, previous)
    env.checks(GREEN)
    item, where = env.start_fix(changes={"app.py": "print('x')\n"})
    synced = env.repo.forge("sync", cwd=where)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    for host in (".codex", ".claude"):
        text = " ".join((where / host / "skills/app-baseline/SKILL.md").read_text("utf-8").split())
        assert ("A background refresh keeps the screen. Show the loading state only when there is "
                "no data yet. On a refetch, keep the shown data, scroll position, open sections, "
                "selection, focus and typed text, and change only what changed. A browser test "
                "scrolls, opens a section, lets two refetches pass and checks both.") in text, host
        assert "Page, sort, filters, search and the open tab of a detail page live in the URL." in text, host
