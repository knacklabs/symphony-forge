"""Worker turns re-read the coordinator guide, searched the whole repo, asked whether a problem
needed a separate fix or a recorded narrow choice, and failed first reviews. The brief now points
at the plan's files, answers both questions in advance and ends with the reviewer's checklist."""
import shutil
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_task import story
from test_worker import calls, install_claude
from test_workers_leave_settings_to_coordinator import client  # noqa: F401

STORY = "worker-brief-faster"


@pytest.fixture(params=[False, True], ids=["fresh", "pre-upgrade-session"])
def brief(client, request, tmp_path):
    log = install_claude(client)
    client.write("tests/test_existing_api.py", "# Existing tests for src/api/handlers.py\n")
    story(client)
    assert client.forge("task", "start", "BOARD/API").returncode == 0
    command = client.bin / "forge"
    current = command.read_text("utf-8")
    if request.param:
        # The session starts with shipped old prompt bytes, before the new guidance exists.
        old_src = tmp_path / "before-worker-guidance"
        shutil.copytree(ROOT / "src/forge", old_src / "forge",
                        ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "tests/fixtures/worker-brief-before-delegation.md",
                        old_src / "forge/templates/brief.md")
        _install(client.bin, "forge", FORGE_SHIM.format(python=sys.executable, src=str(old_src)))
    try:
        worked = client.forge("work", "BOARD/API")
        assert worked.returncode == 0, worked.stdout + worked.stderr
    finally:
        command.write_text(current, encoding="utf-8")
    first = calls(log)[-1]["brief"]
    if request.param:
        assert "Do not read the coordinator guide" not in first
        folder = client.path.parent / f"{client.path.name}-BOARD-API"
        synced = client.forge("sync", cwd=folder)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        worked = client.forge("work", "BOARD/API", "--note", "Fix findings inside Done-when")
        assert worked.returncode == 0, worked.stdout + worked.stderr
        started, resumed = calls(log)
        assert "--resume" in resumed["args"]
        assert (resumed["args"][resumed["args"].index("--resume") + 1]
                == started["args"][started["args"].index("--session-id") + 1])
    return calls(log)[-1]["brief"]


def flat(text):
    return " ".join(text.split())


def test_1_brief_names_the_plan_files_and_skips_the_coordinator_guide(brief):
    text = flat(brief)
    assert ("Do not read the coordinator guide (the forge skill's `SKILL.md`): this brief has "
            "everything a worker needs. Start from the files and tests this brief names, and "
            "search the rest of the repo only for what they call or what calls them.") in text
    assert "`src/api/**`" in text and "`tests/test_api.py`" in text
    assert "`tests/test_existing_api.py`" in text


def test_2_brief_answers_separate_fix_and_narrow_choice_in_advance(brief):
    text = flat(brief)
    assert ("Otherwise, fix the findings inside your Done-when in this round, including new "
            "findings after a recorded narrow or split;") in text
    assert "Otherwise, fix the findings in this round" not in text
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
