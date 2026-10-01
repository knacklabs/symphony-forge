"""Host hooks find forge in uv's tool folder when the host runs them with a bare PATH, as Codex does."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

from test_setup import _hook_commands, _on_a_branch_with_forge_toml

STORY = "hook-path"
BARE_PATH = "/usr/bin:/bin"
SAMPLES = {
    "SessionStart": {"source": "startup"},
    "PreToolUse": {"tool_name": "Bash", "tool_input": {"command": "pwd"}},
    "PostToolUse": {"tool_name": "forge-test", "tool_input": {}, "tool_response": {}},
}


def _synced(repo) -> list[tuple[str, str, str]]:
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    commands = _hook_commands(repo.path)
    assert {rel for rel, _, _ in commands} == {".claude/settings.json", ".codex/hooks.json"}
    return commands


def _run(command: str, event: str, top: Path, home: Path) -> subprocess.CompletedProcess[str]:
    payload = {"session_id": "forge-test", "cwd": str(top), "hook_event_name": event,
               **SAMPLES.get(event, {})}
    return subprocess.run(["/bin/sh", "-c", command], cwd=top, input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60,
                          env={"PATH": BARE_PATH, "HOME": str(home)})


@pytest.mark.skipif(shutil.which("forge", path=BARE_PATH) is not None,
                    reason="this machine has a forge on the bare PATH itself")
def test_synced_hook_commands_find_forge_in_home_local_bin(repo, tmp_path):
    commands = _synced(repo)
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    shutil.copy2(repo.bin / "forge", home / ".local/bin/forge")  # where uv tool install puts it

    for rel, event, command in commands:
        done = _run(command, event, repo.path, home)
        assert done.returncode == 0, (rel, event, done.stdout, done.stderr)
        assert "not found" not in done.stderr, (rel, event, done.stderr)


@pytest.mark.skipif(shutil.which("forge", path=BARE_PATH) is not None,
                    reason="this machine has a forge on the bare PATH itself")
def test_synced_hook_commands_still_block_when_forge_is_nowhere(repo, tmp_path):
    commands = _synced(repo)
    home = tmp_path / "empty-home"
    home.mkdir()

    for rel, event, command in commands:
        done = _run(command, event, repo.path, home)
        assert done.returncode == 2, (rel, event, done.stdout, done.stderr)
