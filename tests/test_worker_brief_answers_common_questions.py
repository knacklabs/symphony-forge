"""Worker turns re-read the coordinator guide, searched the whole repo, asked whether a problem
needed a separate fix or a recorded narrow choice, and failed first reviews. The brief now points
at the plan's files, answers both questions in advance and ends with the reviewer's checklist."""
import pytest

from test_task import story
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "worker-brief-faster"


@pytest.fixture
def brief(client):
    log = install_claude(client)
    story(client)
    assert client.forge("task", "start", "BOARD/API").returncode == 0
    worked = client.forge("work", "BOARD/API")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    return calls(log)[-1]["brief"]


def flat(text):
    return " ".join(text.split())


def test_1_brief_names_the_plan_files_and_skips_the_coordinator_guide(brief):
    text = flat(brief)
    assert "`src/api/**`" in text and "`tests/test_api.py`" in text
    assert ("Do not read the coordinator guide (the forge skill's `SKILL.md`): this brief has "
            "everything a worker needs. Start from the files and tests this brief names, and "
            "search the rest of the repo only for what they call or what calls them.") in text


def test_2_brief_answers_separate_fix_and_narrow_choice_in_advance(brief):
    text = flat(brief)
    assert ("Never ask whether a problem needs a separate fix: a problem outside your Done-when "
            "is a `Spotted:` line.") in text
    assert ("Never ask to record a narrow choice: fix only the review findings inside your "
            "Done-when, and list each other finding in the `Proof list:` as "
            "`Outside Done-when: <finding> - <why>`.") in text


def test_3_brief_ends_with_the_reviewers_checklist(brief):
    last = brief.rsplit("\n## ", 1)[1]
    assert last.startswith("Before you hand over\n")
    for check in ("Every Done-when item you cover", "fails without your change",
                  "`Proof list:`", "No new dependency", "`## Review rules`", "committed"):
        assert check in flat(last), check
