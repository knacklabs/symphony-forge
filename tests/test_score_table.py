"""Every stop question shows the open notes as one table ranked by score, and the guide carries
the table rule and the coordinator's rule.

Runs the real close, read, next and sync commands on a repo made by forge init and on the
earlier-release adopted fixture moved to this release. Only Autoreview, the reader and GitHub are
stubbed; they write the scored findings and notes.
"""
from __future__ import annotations

import pytest

from test_close import blocked, env  # noqa: F401 (env is a fixture)
from test_score_bar import CASES, _client_on_this_release, _round, _says
from test_score_notes import _scored
from test_story import DOC, new_story

STORY = "FORGE-SCORE-1"
HEAD = ["| # | Problem, for whom | Gain | Work | Harm | Proposed |", "|---|---|---|---|---|---|"]


def _table(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith("|")]


@pytest.mark.parametrize("case", CASES)
def test_5_stop_questions_rank_open_notes_in_one_table(env, tmp_path, case):
    _client_on_this_release(env, tmp_path, case)
    repo = env.repo

    # The guide arrives with the table rule and the coordinator's rule, and without the old rules.
    for host in (".claude", ".codex"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "shows the open notes as one table ranked by score" in guide
        assert ("The coordinator settles a reversible note with Harm 1 or 2 itself and tells the owner "
                "after, in one line.") in guide
        assert "never a dismissal for being unnecessary, rare or low value" not in guide
        assert "whatever files they were in" not in guide

    # A review loop stops: its open findings ranked by the bar, then Harm and Gain, each with its own number.
    item, where = env.start_fix()
    at_bar = lambda title, number: _scored("P1", title, "Gain 3, Work 2, Harm 1\nRaise: Functional",  # noqa: E731
                                           f"docs/{number}.md")
    for number in (1, 2):
        _round(env, item, where, number, at_bar(f"Round {number} defect", number))
    _round(env, item, where, 3,
           _scored("P2", "Other shells", "Gain 3, Work 4, Harm 3\nRaise: Functional. Fish users get no prompt.", "docs/3.md"),
           _scored("P1", "Saving drops the basket", "Gain 3, Work 2, Harm 2\nRaise: Functional. Returning shoppers lose it.", "docs/4.md"),
           _scored("P1", "Checkout charges twice", "Gain 5, Work 3, Harm 1\nRaise: Functional. Every buyer pays double.", "docs/5.md"),
           _scored("P1", "The label is long", "Gain 2, Work 1, Harm 1\nRaise: Functional", "docs/6.md"))
    rows = [*HEAD,
            "| 3 | Checkout charges twice: every buyer pays double. | 5 | 3 | 1 | fix now |",
            "| 2 | Saving drops the basket: returning shoppers lose it. | 3 | 2 | 2 | fix this round |",
            "| 1 | Other shells: fish users get no prompt. | 3 | 4 | 3 | follow-up fix |"]
    stop = _round(env, item, where, 4).stderr
    assert _table(stop) == rows, stop
    assert "Accept, narrow or split?" in stop.split(rows[-1], 1)[1]
    assert "\n".join(rows) in repo.forge("next").stdout

    # A read loop stops: its blocking notes in the same ranked table, numbered as the read notes number them.
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    for number in (1, 2, 3):
        _says(repo, f"1. Blocking: Gap {number}.\n   Raise: Not done. Builders guess the limit.\n   Gain 3, Work 1, Harm 1\n"
              + ("2. Blocking: Saved baskets vanish.\n   Raise: Not done. Shoppers lose them overnight.\n   Gain 4, Work 2, Harm 4\n"
                 if number == 3 else ""))
        read = repo.forge("read", "SHOP")
        if number < 3:
            notes = shop / "plans/SHOP.read.md"
            notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - fine\n", encoding="utf-8")
    rows = [*HEAD,
            "| 4 | Saved baskets vanish: shoppers lose them overnight. | 4 | 2 | 4 | fix now |",
            "| 3 | Gap 3: builders guess the limit. | 3 | 1 | 1 | fix this round |"]
    assert read.returncode == 1 and _table(read.stderr) == rows, read.stdout + read.stderr
    assert "\n".join(rows) in repo.forge("next", cwd=shop).stdout
