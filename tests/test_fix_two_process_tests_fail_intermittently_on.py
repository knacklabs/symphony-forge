"""Process cleanup for interrupted Codex work and a crashed cold read."""
from __future__ import annotations

import json

import os
import signal

import pytest

from test_codex_record import _codex_repo_direct, _crash, _down, _held, _up
from test_codex_worker import ROOT, _toml, sdk_data  # noqa: F401 (a fixture)
from test_story import DOC, new_story, setup
from conftest import _install


STORY = "two-process-tests-fail-intermittently-on"


@pytest.mark.skipif(os.name == "nt", reason="the signal scenario requires POSIX")
def test_1_interrupted_work_releases_its_lock_and_processes(repo, monkeypatch, sdk_data):
    _folder, calls = _codex_repo_direct(repo, monkeypatch, sdk_data)
    record = repo.path / ".git/forge/threads/task/BOARD/PAGE.json"
    work, saved, server = _held(repo, calls, record, "stall")
    try:
        work.send_signal(signal.SIGINT)
        work.communicate(timeout=20)
        assert not record.with_suffix(".lock").exists()
        assert _down(server) and _down(saved["driver"]["pid"])
    finally:
        if work.poll() is None:
            work.kill()
            work.communicate()


@pytest.mark.skipif(os.name == "nt", reason="the crash scenario requires POSIX")
def test_2_crashed_cold_read_releases_its_processes(repo, monkeypatch, sdk_data):
    setup(repo, keys=("SHOP",))
    _install(repo.bin, "codex-app-server",
             (ROOT / "tests/stubs/codex-app-server").read_text(encoding="utf-8"))
    monkeypatch.setenv("CODEX_BIN", str(repo.bin / "codex-app-server"))
    monkeypatch.setenv("XDG_DATA_HOME", str(sdk_data))
    home = repo.path.parent / "codex-home"
    home.mkdir()
    monkeypatch.setenv("CODEX_HOME", str(home))
    # Codex runs project hooks, Forge's guard among them, only in a project it trusts.
    (home / "config.toml").write_text(
        f'[projects.{json.dumps(str(repo.path))}]\ntrust_level = "trusted"\n', encoding="utf-8")
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.delenv("CODEX_THREAD_ID")
    shop = new_story(repo, "SHOP")
    (shop / "plans/SHOP.md").write_text(DOC, encoding="utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    (shop / "forge.toml").write_text(_toml(version, "claude", {
        "grill.codex": {"model": "gpt-6-sol", "effort": "high"},
        "grill.claude": {"model": "opus", "effort": "high"},
    }), encoding="utf-8")
    record = repo.path / ".git/forge/threads/read/SHOP.json"
    calls = repo.bin / "codex-app-server.jsonl"
    crashed, saved, server = _held(repo, calls, record, "stall", "read", "SHOP", cwd=shop)
    _crash(crashed, saved)
    assert _up(saved["driver"]["pid"]) and _up(server)
    cleaned = repo.forge("doctor", cwd=shop)
    assert "Stopped the Codex processes that a crashed forge read SHOP left" in cleaned.stdout
    assert _down(server) and _down(saved["driver"]["pid"])
    assert not (shop / "plans/SHOP.read.md").exists()
