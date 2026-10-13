"""A repo that upgrades mid-change keeps its saved unscored reads and reviews holding work back
until their next round scores them; a new repo scores from its first read and review.

Runs the real read, next, work and close commands on a repo made by forge init and on the
earlier-release adopted fixture moved to this release. Only Autoreview, the cold reader, the
worker and GitHub are stubbed.
"""
from __future__ import annotations

import pytest

from conftest import ROOT
from test_close import blocked, env  # noqa: F401 (env is a fixture)
from test_score_bar import _client_on_this_release, _findings_in, _says
from test_score_notes import _scored
from test_story import DOC, new_story
from test_worker import calls, install_claude

STORY = "FORGE-SCORE-1"


@pytest.mark.parametrize("case", ["init", "earlier-adoption-upgrade-sync"])
def test_6_saved_unscored_notes_hold_until_scored_and_the_readme_explains_the_bar(env, tmp_path, case):
    repo = env.repo
    upgraded = case != "init"
    _client_on_this_release(env, tmp_path, case)
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    notes = shop / "plans/SHOP.read.md"
    if upgraded:
        # A read the earlier release saved: a blocking note with no scores still holds the story.
        _says(repo, "1. Blocking: Saving requires an account but sign-in is out of scope.\n")
        read = repo.forge("read", "SHOP")
        assert read.returncode == 0, read.stdout + read.stderr
        assert "finding 1" in repo.forge("next").stdout
        notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep because sign-in is "
                         "out of scope\n", encoding="utf-8")
    # A scored round: the bar decides, so a note labelled blocking but below the bar passes.
    _says(repo, "2. Blocking: The title could be shorter.\n   Raise: Plan gap\n   Gain 2, Work 1, Harm 1\n")
    read = repo.forge("read", "SHOP")
    assert read.returncode == 0, read.stdout + read.stderr
    assert "passed: yes\n" in notes.read_text("utf-8")
    assert "forge read SHOP" not in repo.forge("next").stdout

    # A review the earlier release saved: its unscored P1 still holds work by priority.
    saved = {"commit": "0" * 40, "status": "blocked", "dismissals": [], "blocking_level": "P1",
             "findings": [{"priority": "P1", "title": "Saved serious finding", "body": "Evidence",
                           "file": "app.py", "line": 1}]}
    log = install_claude(repo)
    item, _ = env.start_fix(**({"review": saved} if upgraded else {}))
    if upgraded:
        assert repo.forge("work", item).returncode == 0
        assert "Saved serious finding" in _findings_in(calls(log)[-1]["brief"])
    # A scored round: a P1 below the bar no longer holds the change.
    env.reviews(blocked(_scored("P1", "The button label is long", "Gain 2, Work 1, Harm 1\nRaise: Functional")))
    closed = env.close(item)
    assert closed.returncode == 0, closed.stdout + closed.stderr
    assert "Ready:" in closed.stdout

    readme = (ROOT / "README.md").read_text("utf-8").split("## How Forge weighs a note", 1)[1]
    readme = readme.split("\n## ", 1)[0]
    for text in ("**Gain**", "**Work**", "**Harm**", "| Harm 4 or 5, or Gain 5 |",
                 "| Gain 3 or 4, and Work 1 or 2 |", "| Gain 3 or 4, and Work 3 or more |",
                 "| Gain 1 or 2 |", "breaks Go repos", "Harm 4 (floor: migration)",
                 "This sentence in the plan is not clear"):
        assert text in readme
