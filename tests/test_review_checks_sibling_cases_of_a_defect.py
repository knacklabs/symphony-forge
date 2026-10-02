"""A review that finds a defect checks its sibling cases and reports them in one finding."""
from __future__ import annotations

from test_close import env  # noqa: F401 (pytest fixture)
from test_fix_a_repo_s_own_review_rules_such_as_which import flat

STORY = "FIX-REVIEWS-FIND-ONE-MORE-CASE-OF-THE-SAME-D"

WANTED = ("That means checking every sibling case of the same kind, too: the other states, the "
          "other providers and the other callers of the same code. Report them together in one "
          "finding that names each place.")


def test_1_the_review_prompt_asks_for_every_sibling_case_in_one_finding(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0, "fix close"
    assert WANTED in flat(env.prompt())
    item, _ = env.start_approved_task(env.repo.path.joinpath("plans/SHOP.md").read_text("utf-8"))
    assert env.close(item).returncode == 0, "task close"
    assert WANTED in flat(env.prompt())
