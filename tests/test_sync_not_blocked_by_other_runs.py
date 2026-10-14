"""forge sync refreshes generated files while another item's forge work or land runs, leaves only
that item's chat to the run that holds it, saying so in one line, and still keeps the others'."""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time

import pytest

from conftest import ROOT, _install

from test_codex_record import _saved
from test_codex_worker import sdk_data  # noqa: F401 (a fixture)
from test_worker_and_reader_chats_survive_rounds import (_chat, _old_round, _previous_release,
                                                       _work, _worker)

STORY = "sync-not-blocked"


@pytest.mark.skipif(os.name == "nt", reason="the held run is stopped with Ctrl-C")
@pytest.mark.parametrize("command", ["work", "land"])
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2-client"])
def test_1_sync_runs_while_another_items_run_holds_its_lock(repo, gh, monkeypatch, sdk_data, tmp_path,
                                                          adopted, command):
    # A client fix whose chat an earlier release left only on this machine.
    folder, item, log, _ = _worker(repo, monkeypatch, sdk_data, "codex", "fix", adopted)
    _old_round(repo, tmp_path, folder, "work", item)
    first = _chat(log, "codex")
    started = repo.forge("fix", "start", "Tidy the footer", "--done", "Footer is tidy")
    assert started.returncode == 0, started.stdout + started.stderr
    gh.respond("pr", "list", stdout="[]")  # land asks for the fix's pull request first
    footer = repo.path / ".git/forge/threads/fix/tidy-the-footer.json"
    # The other run is held before its Codex starts, while its chat is not yet on its branch.
    resuming = (repo.bin / "codex-app-server").read_text("utf-8")
    _install(repo.bin, "codex-app-server",
             f"#!{sys.executable}\n" + (ROOT / "tests/stubs/codex-app-server").read_text("utf-8").split("\n", 1)[1])
    held = subprocess.Popen([sys.executable, str(repo.bin / "forge"), command, "tidy-the-footer"],
                            cwd=repo.path, env={**os.environ, "STUB_CODEX_STATUS": "stall"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 60
        while "app_server" not in _saved(footer):  # its Codex is up and on record
            assert time.monotonic() < deadline and held.poll() is None, held.communicate()[1]
            time.sleep(0.05)
        other = tmp_path / "upgrade checkout"
        repo.git("worktree", "add", "-qb", "fix/upgrade", str(other), "main")
        (other / ".claude/skills/forge/SKILL.md").unlink(missing_ok=True)
        synced = repo.forge("sync", cwd=other)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (other / ".claude/skills/forge/SKILL.md").is_file()
        assert [line for line in synced.stdout.splitlines() if "chat alone" in line] == [
            "Left tidy-the-footer's chat alone: forge work tidy-the-footer is running and keeps it."]
    finally:
        held.send_signal(signal.SIGINT)
        held.communicate(timeout=30)
        _install(repo.bin, "codex-app-server", resuming)
    # The unheld fix's chat moved into its branch, so it survives losing this machine's records.
    shutil.rmtree(repo.path / ".git/forge")
    _work(repo, item)
    assert _chat(log, "codex", resumed=True) == first


@pytest.mark.skipif(os.name == "nt", reason="the held run is stopped with Ctrl-C")
@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "adopted-v1.2.2-client"])
def test_2_sync_never_skips_a_chat_an_earlier_release_run_holds(repo, monkeypatch, sdk_data, tmp_path,
                                                               adopted):
    folder, item, _, _ = _worker(repo, monkeypatch, sdk_data, "codex", "fix", adopted)
    _previous_release(repo, tmp_path)
    _install(repo.bin, "codex-app-server",
             f"#!{sys.executable}\n" + (ROOT / "tests/stubs/codex-app-server").read_text("utf-8").split("\n", 1)[1])
    # An earlier release's forge work, mid-upgrade: it holds the fix's lock and never commits its chat.
    config = folder / "forge.toml"
    current = config.read_text("utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    config.write_text(current.replace(f'version = "{version}"', 'version = "v1.2.2"'), encoding="utf-8")
    installed = (repo.bin / "forge").read_text("utf-8")
    _install(repo.bin, "forge", (repo.bin / "old-forge").read_text("utf-8"))
    record = repo.path / f".git/forge/threads/fix/{item}.json"
    held = subprocess.Popen([sys.executable, str(repo.bin / "old-forge"), "work", item], cwd=folder,
                            env={**os.environ, "STUB_CODEX_STATUS": "stall"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True)
    try:
        deadline = time.monotonic() + 60
        while "app_server" not in _saved(record):
            assert time.monotonic() < deadline and held.poll() is None, held.communicate()[1]
            time.sleep(0.05)
        _install(repo.bin, "forge", installed)
        config.write_text(current, encoding="utf-8")
        other = tmp_path / "upgrade checkout"
        repo.git("worktree", "add", "-qb", "fix/upgrade", str(other), "main")
        synced = repo.forge("sync", cwd=other)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        assert (
            f"Warning: forge work {item} is running on an earlier Forge release, which doesn't save its own "
            "chat, so sync can't move that chat yet.\n"
            f"Next: let forge work {item} finish, then forge sync\n") in synced.stdout
    finally:
        held.send_signal(signal.SIGINT)
        held.communicate(timeout=30)
        _install(repo.bin, "forge", installed)
        config.write_text(current, encoding="utf-8")
