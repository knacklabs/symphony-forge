"""The review never counts Forge's own records as the change's files, and asks for every instance of
a kind of defect in one finding."""
from __future__ import annotations

from test_close import env  # noqa: F401 (pytest fixture)
from test_fix_a_repo_s_own_review_rules_such_as_which import flat

STORY = "FIX-REVIEWS-FLAG-FORGE-S-OWN-RECORDS-THE-ITE"

RECORDS = ".factory/stories/SHOP/tasks/T1.json"


def _outside(prompt: str) -> str:
    return prompt.split("Files the branch changes outside that scope:", 1)[1].split("\n\n", 1)[0]


def test_1_a_task_s_own_records_are_not_listed_outside_scope(env):
    item, where = env.start_approved_task(env.repo.path.joinpath("plans/SHOP.md").read_text("utf-8"))
    env.commit(where, "plans/roadmap.json", '{"items": [{"key": "SHOP"}, {"key": "NEXT"}]}\n',
               "Roadmap")
    env.commit(where, "plans/SHOP.read.md", "# Read notes\n\nNothing found.\n", "Read notes")
    changed = env.repo.git("diff", "--name-only", "origin/main...HEAD", cwd=where).splitlines()
    assert RECORDS in changed, "the task's own state file is on its branch"
    assert env.close(item).returncode == 0
    prompt = env.prompt()
    outside = _outside(prompt)
    assert "- other.py" in outside, "a product file outside Scope is still listed"
    for record in (RECORDS, "plans/roadmap.json", "plans/SHOP.read.md"):
        assert record not in outside, record
    assert ("Forge's own records (everything under `.factory/`, `plans/roadmap.json`, the "
            "story's doc and its read notes) are not part of the change: never report them as files outside "
            "Scope or as unrelated changes.") in flat(prompt)


def test_2_the_review_reports_every_instance_of_a_defect_together(env):
    item, _ = env.start_fix()
    assert env.close(item).returncode == 0, "fix close"
    wanted = ("When you find a kind of defect, look for every other place in the change with the "
              "same defect and report them all in one finding that names each place, not one "
              "place per round.")
    assert wanted in flat(env.prompt())
    item, _ = env.start_approved_task(env.repo.path.joinpath("plans/SHOP.md").read_text("utf-8"))
    assert env.close(item).returncode == 0, "task close"
    assert wanted in flat(env.prompt())
