"""Host hooks run forge when the host gives them a bare PATH, as Codex does, and never leave a
machine blocked just because forge isn't on that PATH."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from test_setup import _executable, _hook_commands, _on_a_branch_with_forge_toml, _version

STORY = "hook-path"
BARE_PATH = "/usr/bin:/bin"
SAMPLES = {
    "SessionStart": {"source": "startup"},
    "PreToolUse": {"tool_name": "Bash", "tool_input": {"command": "pwd"}},
    "PostToolUse": {"tool_name": "forge-test", "tool_input": {}, "tool_response": {}},
}
# The hooks always look in these too. On macOS a sandbox hides them; elsewhere a machine with forge
# or uv there has no "nothing installed".
SYSTEM = ("/usr/local", "/opt/homebrew")
HIDE = (["sandbox-exec", "-p", "(version 1)(allow default)(deny file-read* "
         + " ".join(f'(subpath "{folder}")' for folder in SYSTEM) + ")"]
        if shutil.which("sandbox-exec") else [])
INSTALLED = [] if HIDE else [str(path) for path in (
    Path(folder) / "bin" / name for folder in SYSTEM for name in ("forge", "uv", "uvx")) if path.exists()]

pytestmark = pytest.mark.skipif(os.name == "nt", reason="hooks run under sh with POSIX folders")


def _synced(repo) -> list[tuple[str, str, str]]:
    _on_a_branch_with_forge_toml(repo)
    assert repo.forge("sync").returncode == 0
    commands = _hook_commands(repo.path)
    assert {rel for rel, _, _ in commands} == {".claude/settings.json", ".codex/hooks.json"}
    return commands


def _home(tmp_path: Path, **tools: str) -> Path:
    """A HOME whose .local/bin, where uv installs tools, holds these programs."""
    home = tmp_path / "home"
    (home / ".local/bin").mkdir(parents=True)
    for name, text in tools.items():
        _executable(home / ".local/bin" / name, text)
    return home


def _logging(tmp_path: Path, name: str) -> tuple[str, Path]:
    """A stub of uv or uvx that logs its folder and arguments, at the edge where uv fetches."""
    log = tmp_path / f"{name}.log"
    return f'#!/bin/sh\necho "$PWD $*" >> "{log.as_posix()}"\ncat > /dev/null\n', log


def _run(command: str, event: str, top: Path, home: Path, hide: list[str] | None = None,
         **env: str) -> subprocess.CompletedProcess[str]:
    payload = {"session_id": "forge-test", "cwd": str(top), "hook_event_name": event,
               **SAMPLES.get(event, {})}
    return subprocess.run([*(hide or []), "/bin/sh", "-c", command], cwd=top, input=json.dumps(payload),
                          capture_output=True, text=True, timeout=60,
                          env={"PATH": BARE_PATH, "HOME": str(home), **env})


def _all_run(commands, top: Path, home: Path, **env: str) -> None:
    for rel, event, command in commands:
        done = _run(command, event, top, home, **env)
        assert done.returncode == 0, (rel, event, done.stdout, done.stderr)
        assert "not found" not in done.stderr, (rel, event, done.stderr)


def test_1_hooks_find_forge_in_home_local_bin(repo, tmp_path):
    commands = _synced(repo)
    home = _home(tmp_path, forge=(repo.bin / "forge").read_text(encoding="utf-8"))
    _all_run(commands, repo.path, home)


def test_2_hooks_find_forge_in_uv_tool_bin_dir(repo, tmp_path):
    commands = _synced(repo)
    folder = tmp_path / "uv-tools"
    folder.mkdir()
    shutil.copy2(repo.bin / "forge", folder / "forge")
    _all_run(commands, repo.path, _home(tmp_path), UV_TOOL_BIN_DIR=str(folder))


def test_3_hooks_without_forge_run_the_pinned_release_through_uvx(repo, tmp_path):
    commands = _synced(repo)
    stub, log = _logging(tmp_path, "uvx")
    _all_run(commands, repo.path, _home(tmp_path, uvx=stub))
    release = f"--from git+https://github.com/knacklabs/symphony-forge@v{_version(repo).removeprefix('v')}"
    assert log.read_text(encoding="utf-8").splitlines() == [
        f"{repo.path} -q {release} forge hook {hook}"
        for hook in ("context", "handoff", "deny", "approval") * 2]


@pytest.mark.skipif(bool(INSTALLED), reason=f"hooks always search {', '.join(INSTALLED)}")
def test_4_with_nothing_installed_hooks_block_with_one_plain_line(repo, tmp_path):
    commands = _synced(repo)
    pinned = "v" + _version(repo).removeprefix("v")
    home = _home(tmp_path)
    assert len(commands) == 8
    for rel, event, command in commands:
        done = _run(command, event, repo.path, home, HIDE)
        assert done.returncode == 2, (rel, event, done.stdout, done.stderr)
        assert done.stderr == (
            "Forge isn't installed, so this hook can't run; install it with uv tool install "
            f"git+https://github.com/knacklabs/symphony-forge@{pinned}, then run forge doctor.\n")


def test_5_doctor_reports_a_hook_that_cant_run_with_a_bare_path(repo, tmp_path, monkeypatch):
    _synced(repo)
    # forge is on the test's own PATH, but not where a hook with PATH=/usr/bin:/bin looks; the
    # pinned release can't be fetched either.
    empty = tmp_path / "empty"
    empty.mkdir()
    monkeypatch.setenv("XDG_BIN_HOME", str(empty))
    monkeypatch.setenv("HOME", str(_home(tmp_path, uvx="#!/bin/sh\necho 'uvx: no network' >&2\nexit 1\n")))
    done = repo.forge("doctor")
    assert done.returncode != 0
    for rel in (".claude/settings.json", ".codex/hooks.json"):
        assert (f"The PreToolUse hook in {rel} fails with exit code 2 when run with "
                f"PATH={BARE_PATH}: uvx: no network") in done.stdout, done.stdout


def test_6_doctor_never_runs_a_launcher_that_differs_from_sync_s(repo, tmp_path):
    _synced(repo)
    marker = tmp_path / "launcher-ran"
    launcher = repo.path / ".forge/hooks.sh"
    launcher.write_text(launcher.read_text(encoding="utf-8") + f'echo ran > "{marker.as_posix()}"\n',
                        encoding="utf-8")
    done = repo.forge("doctor")
    assert done.returncode != 0
    assert ("doctor didn't run the host hooks, because .forge/hooks.sh differs from what forge "
            "sync writes.") in done.stdout, done.stdout
    assert not marker.exists()
