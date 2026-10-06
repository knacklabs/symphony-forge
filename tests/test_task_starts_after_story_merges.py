"""Story starts follow content history and the same overlap rules as forge next.

Command regressions own the squash-date, automatic merge and overlap contracts;
client commands prove the coordinator guidance reaches both installation paths.
"""
import shutil

import pytest

from conftest import ROOT
from test_close import env  # noqa: F401
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo
from test_plan_edits_on_the_default_branch import _saved
from test_readloop_gates import read
from test_task import DOC, story
from test_upgrade_command import RELEASE, unsynced_up  # noqa: F401

STORY = "FIX-AFTER-A-STORY-PART-MERGES-STARTING-THE-N"


def test_1_older_content_on_main_does_not_refuse_a_new_story_copy(repo, claude_payload, monkeypatch):
    shop = _saved(repo, claude_payload)
    doc = shop / "plans/SHOP.md"
    doc.write_text(doc.read_text("utf-8").replace("People lose", "Shoppers lose"), "utf-8")
    # Commit dates deliberately disagree with content history after the squash.
    with monkeypatch.context() as dated:
        dated.setenv("GIT_COMMITTER_DATE", "2001-01-01T00:00:00")
        repo.git("commit", "-qam", "Clarify the story", cwd=shop)
        read(repo)
    shown = repo.forge("next")
    assert "Next: forge task start SHOP/SHOW" in shown.stdout, shown.stdout + shown.stderr
    started = repo.forge("task", "start", "SHOP/SHOW")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "Shoppers lose" in repo.git("show", "task/SHOP-SHOW:plans/SHOP.md")


def test_2_only_a_story_doc_difference_is_merged_into_the_story(repo):
    story(repo)
    repo.git("merge", "-q", "--ff-only", "story/BOARD")
    changed = DOC.replace("Reuse the old board's look.", "Keep the familiar board layout.")
    repo.write("plans/BOARD.md", changed)
    repo.git("commit", "-qam", "Clarify the builder notes")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("task", "start", "BOARD/HELP")
    assert started.returncode == 0, started.stdout + started.stderr
    assert "Merged origin/main into story/BOARD" in started.stdout
    assert repo.git("show", "story/BOARD:plans/BOARD.md") == changed.strip()
    assert repo.git("merge-base", "story/BOARD", "origin/main") == repo.git("rev-parse", "origin/main")
    assert repo.git("show", "task/BOARD-HELP:plans/BOARD.md") == changed.strip()


@pytest.mark.parametrize("other_story", [False, True], ids=["same-story", "another-story"])
def test_3_next_names_the_unmerged_glob_overlap_instead_of_offering_start(repo, other_story):
    story(repo)
    assert repo.forge("task", "start", "BOARD/API").returncode == 0
    key = "OTHER" if other_story else "BOARD"
    if other_story:
        story(repo, key=key)
    repo.git("worktree", "add", "-q", str(repo.path.parent / f"story-{key}"), f"story/{key}")
    shown = repo.forge("next")
    assert shown.returncode == 0, shown.stderr
    assert f"{key}/ROUTES waits for BOARD/API to merge first." in shown.stdout
    assert f"Next: forge task start {key}/ROUTES" not in shown.stdout
    refused = repo.forge("task", "start", f"{key}/ROUTES")
    assert refused.returncode == 1 and "BOARD/API" in refused.stderr


def _guidance(client):
    for host in (".codex", ".claude"):
        text = " ".join((client / host / "skills/forge/SKILL.md").read_text("utf-8").split())
        assert "content history, never commit dates" in text
        assert "only the story doc differs" in text
        assert "unmerged item" in text and "overlapping files" in text


def test_4_new_clients_receive_story_start_guidance(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    _guidance(client)


def test_5_earlier_adopted_clients_receive_story_start_guidance(unsynced_up):
    up = unsynced_up
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", up.repo.path, dirs_exist_ok=True)
    up.repo.git("switch", "-qc", "adoption")
    up.repo.git("add", "-A")
    up.repo.git("commit", "-qm", "Adopt earlier Forge")
    up.repo.git("switch", "-q", "main")
    up.repo.git("merge", "-q", "--ff-only", "adoption")
    up.repo.git("push", "-q", "origin", "main")
    result = up.run(RELEASE)
    assert result.returncode == 0, result.stdout + result.stderr
    _guidance(up.folder)
