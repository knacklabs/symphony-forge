"""Task start owns upgrading an open story, rather than handing out old pins.

Real git and Forge commands protect the inherited release, merge conflict and
matching-pin contracts. Existing task tests never upgrade with an open story.
No production seam or merge fake decides these results (test-audit gate).
"""
import shutil
import tomllib

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version
from test_task import story

STORY = "task-start-pin"


def _open_story(repo, gh, tmp_path, adopted=True, conflict=False):
    version = _version(repo)
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("switch", "-qc", "adoption")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt earlier Forge")
        repo.git("switch", "-q", "main")
        repo.git("merge", "-q", "--ff-only", "adoption")
    else:
        client, initialized = _fresh_client(repo, gh, tmp_path)
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
        repo.path = client
    # Setup commits model releases already landed, rather than new Forge work.
    repo.git("config", "core.hooksPath", str(tmp_path / "no-hooks"))
    # The fresh client also opens its story on the earlier release.
    repo.git("switch", "-qc", "fix/earlier-release")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    pin = tomllib.loads(settings)["version"]
    old = settings.replace(f'version = "{pin}"', 'version = "v1.2.2"')
    repo.write("forge.toml", old)
    repo.git("add", "-A")
    repo.git("commit", "--allow-empty", "-qm", "Use earlier Forge")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/earlier-release")
    story(repo)
    folder = repo.path.parent / "open story with spaces"
    repo.git("worktree", "add", "-q", str(folder), "story/BOARD")
    if conflict:
        (folder / "README.md").write_text("The story's readme\n", "utf-8")
        repo.git("add", "README.md", cwd=folder)
        repo.git("commit", "-qm", "Describe story work", cwd=folder)
    # Land an upgrade's pin, fast command and real sync output without faking git.
    repo.git("switch", "-qc", "fix/upgrade")
    repo.write("forge.toml", old.replace('version = "v1.2.2"', f'version = "{version}"\n'
               'fast_test = "python -c \\"print(456)\\""'))
    if conflict:
        repo.write("README.md", "The upgraded readme\n")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("config", "core.hooksPath", str(tmp_path / "no-hooks-after-sync"))
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Upgrade Forge")
    repo.git("push", "-q", "origin", "fix/upgrade:main")
    # Leave the local default stale: task start must use the fetched default.
    repo.git("config", "core.hooksPath", str(tmp_path / "no-hooks"))
    return folder, version


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2"])
def test_1_task_inherits_the_upgrade_with_an_open_story(repo, gh, tmp_path, adopted):
    folder, version = _open_story(repo, gh, tmp_path, adopted)
    if not adopted:
        repo.git("worktree", "remove", str(folder))
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stdout + started.stderr
    assert repo.git("merge-base", "story/BOARD", "origin/main") == repo.git("rev-parse", "origin/main")
    for branch in ("story/BOARD", "task/BOARD-PAGE"):
        settings = tomllib.loads(repo.git("show", f"{branch}:forge.toml"))
        assert settings["version"] == version
        assert settings["fast_test"] == 'python -c "print(456)"'
    task_folder = repo.path.parent / f"{repo.path.name}-BOARD-PAGE"
    ran = repo.forge("test", cwd=task_folder)
    assert ran.returncode == 0 and "456" in ran.stdout, ran.stdout + ran.stderr
    for host in (".codex", ".claude"):
        skill = (task_folder / host / "skills/forge/SKILL.md").read_text("utf-8")
        assert "Matching release pins need no upgrade merge." in skill
    if adopted:
        assert repo.git("status", "--porcelain", cwd=folder) == ""


def test_2_upgrade_conflict_stops_before_creating_a_task(repo, gh, tmp_path):
    folder, _ = _open_story(repo, gh, tmp_path, conflict=True)
    before = repo.git("rev-parse", "story/BOARD")
    refused = repo.forge("task", "start", "BOARD/PAGE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Resolve the merge conflicts" in refused.stderr
    assert "forge task start BOARD/PAGE" in refused.stderr
    assert folder.as_posix() in refused.stderr.replace("\\", "/")
    assert repo.git("branch", "--list", "task/BOARD-PAGE") == ""
    assert repo.git("rev-parse", "story/BOARD") == before
    assert repo.git("rev-parse", "MERGE_HEAD", cwd=folder) == repo.git("rev-parse", "origin/main")
    pending = repo.forge("task", "start", "BOARD/PAGE")
    assert pending.returncode == 1 and pending.stderr == refused.stderr
    # The printed path works even with spaces; finish the merge and retry.
    (folder / "README.md").write_text("Both changes kept\n", "utf-8")
    repo.git("add", "README.md", cwd=folder)
    repo.git("commit", "-qm", "Resolve the readme", cwd=folder)
    retried = repo.forge("task", "start", "BOARD/PAGE")
    assert retried.returncode == 0, retried.stdout + retried.stderr


def test_3_matching_pins_leave_the_story_unchanged(repo):
    version = _version(repo)
    repo.write("forge.toml", f'version = "{version}"\n')
    repo.git("add", "forge.toml")
    repo.git("commit", "-qm", "Pin Forge")
    story(repo)
    before = repo.git("rev-parse", "story/BOARD")
    repo.write("README.md", "Unrelated default branch change\n")
    repo.git("commit", "-qam", "Edit the readme")
    repo.git("push", "-q", "origin", "main")
    started = repo.forge("task", "start", "BOARD/PAGE")
    assert started.returncode == 0, started.stdout + started.stderr
    assert repo.git("rev-parse", "story/BOARD") == before
    assert repo.git("show", "task/BOARD-PAGE:README.md") == "# A test repo"


def test_4_uncommitted_story_work_is_preserved_before_the_upgrade(repo, gh, tmp_path):
    folder, _ = _open_story(repo, gh, tmp_path)
    before = repo.git("rev-parse", "story/BOARD")
    (folder / "README.md").write_text("Work in progress\n", "utf-8")
    refused = repo.forge("task", "start", "BOARD/PAGE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Commit or stash the changes" in refused.stderr
    assert folder.as_posix() in refused.stderr.replace("\\", "/")
    assert "forge task start BOARD/PAGE" in refused.stderr
    assert repo.git("branch", "--list", "task/BOARD-PAGE") == ""
    assert repo.git("rev-parse", "story/BOARD") == before
    assert (folder / "README.md").read_text("utf-8") == "Work in progress\n"


def test_5_a_refused_merge_commit_reports_the_problem_and_never_starts_old_forge(repo, gh, tmp_path):
    folder, _ = _open_story(repo, gh, tmp_path)
    hooks = tmp_path / "client-hooks"
    hooks.mkdir()
    hook = hooks / "pre-merge-commit"
    hook.write_text('#!/bin/sh\necho "Client merge check failed" >&2\nexit 1\n', "utf-8")
    hook.chmod(0o755)
    repo.git("config", "core.hooksPath", str(hooks))
    refused = repo.forge("task", "start", "BOARD/PAGE")
    assert refused.returncode == 1, refused.stdout + refused.stderr
    assert "Client merge check failed" in refused.stderr
    assert "forge task start BOARD/PAGE" in refused.stderr
    assert folder.as_posix() in refused.stderr.replace("\\", "/")
    assert repo.git("branch", "--list", "task/BOARD-PAGE") == ""
