"""Every stop question shows the open notes as one table ranked by score, and the guide carries
the table rule and the coordinator's rule.

Runs the real close, read, next and sync commands on a repo made by forge init and on the
earlier-release adopted fixture moved to this release. Only Autoreview, the reader and GitHub are
stubbed; they write the scored findings and notes.
"""
from __future__ import annotations

from datetime import datetime, timezone

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

    # The guide arrives with the table rule, the coordinator's rule and the stop rule, and without the old rules.
    for host in (".claude", ".codex"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "shows the open notes as one table ranked by score" in guide
        assert ("The coordinator settles a reversible note with Harm 1 or 2 itself and tells the owner "
                "after, in one line.") in guide
        assert ("The stop rule: the printed stop says who decides. When every open note has Harm 1 or 2, "
                "it says \"Every open note has Harm 1 or 2: settle it yourself") in guide
        assert "never a dismissal for being unnecessary, rare or low value" not in guide
        assert "whatever files they were in" not in guide

    # A review loop stops: every open finding, ranked by the bar, then Harm, then Gain, then Work,
    # each with its own number; one below the bar is listed too.
    item, where = env.start_fix()
    found = lambda title, scores, number, who="": _scored(  # noqa: E731
        "P1", title, f"{scores}\nRaise: Functional.{who}", f"docs/{number}.md")
    for number in (1, 2):
        _round(env, item, where, number, found(f"Round {number} defect", "Gain 3, Work 2, Harm 1", number))
    _round(env, item, where, 3,
           found("Other shells", "Gain 3, Work 4, Harm 3", 3, " Fish users get no prompt."),
           found("Saving drops the basket", "Gain 3, Work 2, Harm 2", 4, " Returning shoppers lose it."),
           found("Checkout charges twice", "Gain 5, Work 3, Harm 1", 5, " Every buyer pays double."),
           found("The label is long", "Gain 2, Work 1, Harm 1", 6, " Readers squint."),
           found("Prices round down", "Gain 4, Work 1, Harm 2", 7, " Sellers lose cents."),
           found("Search skips accents", "Gain 3, Work 1, Harm 2", 8, " Shoppers abroad miss items."),
           found("Coupons stack", "Gain 3, Work 2, Harm 3", 9, " Shops lose money."))
    rows = [*HEAD,
            "| 3 | Checkout charges twice: every buyer pays double. | 5 | 3 | 1 | fix now |",
            "| 7 | Coupons stack: shops lose money. | 3 | 2 | 3 | fix this round |",
            "| 5 | Prices round down: sellers lose cents. | 4 | 1 | 2 | fix this round |",
            "| 6 | Search skips accents: shoppers abroad miss items. | 3 | 1 | 2 | fix this round |",
            "| 2 | Saving drops the basket: returning shoppers lose it. | 3 | 2 | 2 | fix this round |",
            "| 1 | Other shells: fish users get no prompt. | 3 | 4 | 3 | follow-up fix |",
            "| 4 | The label is long: readers squint. | 2 | 1 | 1 | live with |"]
    stop = _round(env, item, where, 4).stderr
    assert _table(stop) == rows, stop
    assert "Accept, narrow or split?" in stop.split(rows[-1], 1)[1]
    # A Harm 3 note is open, so the owner decides.
    assert ("Ask the human to narrow the part, split it, or accept the remaining findings, in these words:"
            in stop and "settle it yourself" not in stop)
    assert "\n".join(rows) in repo.forge("next").stdout

    # A stop with a finding saved before scores and a scored one: every open finding is a plain
    # line, never a partial table.
    old = {"commit": "0" * 40, "status": "blocked", "dismissals": [], "blocking_level": "P1",
           "findings": [{"priority": "P1", "title": "Saved serious finding", "body": "Evidence",
                         "file": "app.py", "line": 1},
                        {"priority": "P1", "title": "Scored finding", "body": "Gain 4, Work 1, Harm 2\nEvidence",
                         "file": "app.py", "line": 2, "gain": 4, "work": 1, "harm": 2}]}
    env.start("old-stop", "fix/old-stop", ".factory/fixes/old-stop.json",
              {"kind": "fix", "why": "Old stop", "done_when": "It stops", "review": old,
               "stop": {"file": "app.py", "at": datetime.now(timezone.utc).isoformat()}}, {"app.py": "x = 1\n"})
    said = repo.forge("next").stdout
    assert ("It still has these problems:\n- Saved serious finding: evidence\n"
            "- Scored finding: evidence\nAccept") in said, said

    # A read loop stops: its blocking notes in the same ranked table, numbered as the read notes number them.
    def read_three(key: str, last: str):
        shop = new_story(repo, key)
        (shop / "plans" / f"{key}.md").write_text(DOC, encoding="utf-8")
        for number in (1, 2, 3):
            _says(repo, f"1. Blocking: Gap {number}.\n   Raise: Not done. Builders guess the limit.\n"
                  + ("   Gain 3, Work 1, Harm 1\n" if key == "SHOP" else "") + (last if number == 3 else ""))
            read = repo.forge("read", key)
            if number < 3:
                notes = shop / "plans" / f"{key}.read.md"
                notes.write_text(notes.read_text("utf-8").rstrip() + "\n   Disposition: keep - fine\n", encoding="utf-8")
        assert read.returncode == 1, read.stdout + read.stderr
        return shop, read.stderr

    note = lambda n, title, scores: f"{n}. Blocking: {title}.\n   Raise: Not done. Shoppers notice.\n   {scores}\n"  # noqa: E731
    shop, stop = read_three("SHOP", note(2, "Saved baskets vanish", "Gain 4, Work 2, Harm 4")
                            + note(3, "Totals drift", "Gain 5, Work 1, Harm 1")
                            + note(4, "Sorting is random", "Gain 3, Work 1, Harm 2")
                            + note(5, "Names are cut", "Gain 4, Work 2, Harm 1")
                            + note(6, "Dates are local", "Gain 3, Work 2, Harm 1"))
    rows = [*HEAD,
            "| 4 | Saved baskets vanish: shoppers notice. | 4 | 2 | 4 | fix now |",
            "| 5 | Totals drift: shoppers notice. | 5 | 1 | 1 | fix now |",
            "| 6 | Sorting is random: shoppers notice. | 3 | 1 | 2 | fix this round |",
            "| 7 | Names are cut: shoppers notice. | 4 | 2 | 1 | fix this round |",
            "| 3 | Gap 3: builders guess the limit. | 3 | 1 | 1 | fix this round |",
            "| 8 | Dates are local: shoppers notice. | 3 | 2 | 1 | fix this round |"]
    assert _table(stop) == rows, stop
    assert "\n".join(rows) in repo.forge("next", cwd=shop).stdout

    # A read note without scores beside a scored one: the read stop lists every note as a plain line.
    _, stop = read_three("BAKE", note(2, "Totals drift", "Gain 5, Work 1, Harm 4"))
    assert ("It still has these problems:\n- Gap 3: builders guess the limit.\n"
            "- Totals drift: shoppers notice.\nAccept") in stop, stop
    assert not _table(stop)
