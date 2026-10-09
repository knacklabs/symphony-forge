"""Laptop installers distinguish an installed Docker CLI from a running engine."""

import os
import re
import shlex
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest

STORY = "FIX-SKIPPED-TEMPLATES"
ROOT = Path(__file__).resolve().parents[1]


def test_windows_installer_is_a_required_pull_request_check():
    # CI routing is a config contract; local execution cannot prove the Windows branch.
    workflow = (ROOT / ".github/workflows/forge-next.yml").read_text(encoding="utf-8")
    assert re.search(r"^  pull_request:\s*$", workflow, re.M)
    job = re.search(r"^  windows-installers:\n(.*?)(?=^  \S|\Z)", workflow, re.M | re.S)
    assert job, "Windows installer cases need a pull-request job"
    assert "runs-on: windows-latest" in job[1]
    assert "if:" not in job[1] and "continue-on-error:" not in job[1]
    command = re.search(r"^      - run: (.+)$", job[1], re.M)
    assert command
    tokens = shlex.split(command[1])
    assert "pytest" in tokens and "tests/test_installers_explain_docker_start.py" in tokens
    assert "-k" not in tokens and "--collect-only" not in tokens
    settings = tomllib.loads((ROOT / "forge.toml").read_text(encoding="utf-8"))
    assert "windows-installers" in settings["checks"]


@pytest.mark.parametrize("check,running,new_install", [
    (True, False, False), (True, True, False),
    (False, False, False), (False, True, False), (False, False, True),
])
def test_installers_check_docker_engine_and_explain_starting_desktop(
        tmp_path, check, running, new_install):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    calls = tmp_path / "docker-calls"
    env = os.environ | {"HOME": str(tmp_path), "LOCALAPPDATA": str(tmp_path),
                        "DOCKER_RUNNING": "0" if not running else "1"}
    if os.name == "nt":
        powershell = shutil.which("powershell")
        assert powershell
        system_root = Path(os.environ["SystemRoot"])
        env |= {"PATH": str(bin_dir) + os.pathsep + str(system_root / "System32"),
                "PATHEXT": ".CMD;.BAT"}
        for name in ("winget", "git", "gh", "node", "uv", "claude", "codex"):
            (bin_dir / f"{name}.cmd").write_text("@echo off\nexit /b 0\n", encoding="utf-8")
        (bin_dir / "forge.cmd").write_text("@echo forge v1.2.8\n", encoding="utf-8")
        (bin_dir / "wsl.cmd").write_text("@echo Default Version: 2\n", encoding="utf-8")
        docker = tmp_path / "docker.cmd" if new_install else bin_dir / "docker.cmd"
        docker.write_text(
            f'@echo off\necho %* >> "{calls.as_posix()}"\n'
            'if "%DOCKER_RUNNING%"=="1" exit /b 0\n'
            'echo Docker daemon unavailable 1>&2\nexit /b 1\n', encoding="utf-8")
        if new_install:
            (bin_dir / "winget.cmd").write_text(
                f'@echo off\ncopy /Y "{docker.as_posix()}" '
                f'"{(bin_dir / "docker.cmd").as_posix()}" >nul\nexit /b 0\n', encoding="utf-8")
        cache = tmp_path / "ms-playwright"
        command = [powershell, "-NoProfile", "-File",
                   str(ROOT / "scripts/install-windows.ps1")]
        if check:
            command.append("-Check")
    else:
        env["PATH"] = str(bin_dir)
        for name in ("brew", "git", "gh", "node", "uv", "claude", "codex"):
            path = bin_dir / name
            path.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            path.chmod(0o755)
        (bin_dir / "forge").write_text('#!/bin/sh\necho "forge v1.2.8"\n', encoding="utf-8")
        (bin_dir / "forge").chmod(0o755)
        docker = tmp_path / "docker" if new_install else bin_dir / "docker"
        docker.write_text(
            f'#!/bin/sh\necho "$*" >> {shlex.quote(calls.as_posix())}\n'
            '[ "$DOCKER_RUNNING" = 1 ] && exit 0\n'
            'echo "Docker daemon unavailable" >&2\nexit 1\n', encoding="utf-8")
        docker.chmod(0o755)
        if new_install:
            (bin_dir / "brew").write_text(
                '#!/bin/sh\n/bin/cp ' + shlex.quote(docker.as_posix()) + ' '
                + shlex.quote((bin_dir / "docker").as_posix()) + '\n', encoding="utf-8")
        cache = tmp_path / "Library/Caches/ms-playwright"
        command = ["/bin/bash", str(ROOT / "scripts/install-mac.sh")]
        if check:
            command.append("--check")
    for kind in ("chromium", "firefox", "webkit"):
        (cache / f"{kind}-1").mkdir(parents=True)
    result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=30)
    assert result.returncode == 0, result.stdout + result.stderr
    if running:
        assert "Start Docker Desktop" not in result.stdout
        if not check:
            assert "Docker is ready." in result.stdout
    else:
        assert "Start Docker Desktop" in result.stdout
        assert "Docker is ready." not in result.stdout
    assert calls.read_text(encoding="utf-8").splitlines() == ["info"]
    assert "Docker daemon unavailable" not in result.stderr
