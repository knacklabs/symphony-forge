"""forge sync refreshes generated files while another item's forge work runs, and leaves only that
item's chat to the run that holds it, saying so in one line."""
from __future__ import annotations

import os
import signal

import pytest

from test_codex_record import _codex_repo_direct, _down, _held
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)
from test_worker_and_reader_chats_survive_rounds import _adopted


@pytest.mark.skipif(os.name == "nt", reason="the held run is stopped with Ctrl-C")
@pytest.mark.parametrize("adopted", [False, True], ids=["new-init", "adopted-v1.2.2-sync"])
def test_sync_runs_while_another_items_work_holds_its_lock(repo, monkeypatch, sdk_data, tmp_path,
                                                          adopted):
    if adopted:
        _adopted(repo)
    _, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    record = repo.path / ".git/forge/threads/task/BOARD/PAGE.json"
    work, _, stub = _held(repo, calls, record, "stall")
    try:
        fix = tmp_path / "another fix"
        repo.git("worktree", "add", "-qb", "fix/another", str(fix), "main")
        (fix / ".claude/skills/forge/SKILL.md").unlink(missing_ok=True)
        synced = repo.forge("sync", cwd=fix)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (fix / ".claude/skills/forge/SKILL.md").is_file()
        assert ("Left BOARD/PAGE's chat alone: forge work BOARD/PAGE is running and keeps it."
                in synced.stdout.splitlines())
    finally:
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=30)
    assert _down(stub)
