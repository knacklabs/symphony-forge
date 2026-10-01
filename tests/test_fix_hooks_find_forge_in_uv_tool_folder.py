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
# The hooks always look in these too, so a machine with forge or uv there has no "nothing installed".
SYSTEM = [Path(folder) / name for folder in ("/usr/local/bin", "/opt/homebrew/bin")
          for name in ("forge", "uv", "uvx")]
INSTALLED = [str(path) for path in SYSTEM if path.exists()] + (
    [] if shutil.which("forge", path=BARE_PATH) is None else ["forge on /usr/bin:/bin"])

pytestmark = pytest.mark.skipif(os.name == "nt", reason="hooks run under sh with POSIX folders")


def _synced(repo, toml: str = "") -> list[tuple[str, str, str]]:
    _on_a_branch_with_forge_toml(repo)
    if toml:
        repo.write("forge.toml", (repo.path / "forge.toml").read_text(encoding="utf-8") + toml)
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


def _run(command: str, event: str, top: Path, home: Path, **env: str) -> subprocess.CompletedProcess[str]:
    payload = {"session_id": "forge-test", "cwd": str(top), "hook_event_name": event,
               **SAMPLES.get(event, {})}
    return subprocess.run(["/bin/sh", "-c", command], cwd=top, input=json.dumps(payload),
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


def test_4_forge_s_own_repo_without_forge_runs_the_checkout_through_uv(repo, tmp_path):
    commands = _synced(repo, 'repo = "forge-source"\n')
    stub, log = _logging(tmp_path, "uv")
    uvx, uvx_log = _logging(tmp_path, "uvx")
    _all_run(commands, repo.path, _home(tmp_path, uv=stub, uvx=uvx))
    for line in log.read_text(encoding="utf-8").splitlines():
        here, _, rest = line.partition(" ")
        assert here == str(repo.path)
        assert rest.startswith("run -q --project ") and " forge hook " in rest
        assert Path(rest.split()[3]).resolve() == repo.path.resolve()
    assert len(log.read_text(encoding="utf-8").splitlines()) == 8
    assert not uvx_log.exists()


@pytest.mark.skipif(bool(INSTALLED), reason=f"hooks always search {', '.join(INSTALLED)}")
def test_5_with_nothing_installed_hooks_block_with_one_plain_line(repo, tmp_path):
    commands = _synced(repo)
    pinned = "v" + _version(repo).removeprefix("v")
    for rel, event, command in commands:
        done = _run(command, event, repo.path, _home(tmp_path))
        assert done.returncode == 2, (rel, event, done.stdout, done.stderr)
        assert done.stderr == (
            "Forge isn't installed, so this hook can't run; install it with uv tool install "
            f"git+https://github.com/knacklabs/symphony-forge@{pinned}, then run forge doctor.\n")


def test_6_doctor_reports_a_hook_that_cant_run_with_a_bare_path(repo, tmp_path, monkeypatch):
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
