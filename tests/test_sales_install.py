"""Sales laptop setup at each script's command-line boundary."""

import os
import shutil
import subprocess
from pathlib import Path

STORY = "FORGE-SALES-1"
ROOT = Path(__file__).resolve().parents[1]


def _stub(folder: Path, name: str, body: str) -> None:
    path = folder / name
    path.write_text("#!/bin/sh\n" + body + "\n", encoding="utf-8")
    path.chmod(0o755)


def _mac_check_and_install(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for name in ("git", "node", "brew"):
        _stub(bin_dir, name, "exit 0")
    env = os.environ | {"PATH": str(bin_dir), "HOME": str(tmp_path)}
    script = ROOT / "scripts/install-mac.sh"

    check = subprocess.run(["/bin/bash", str(script), "--check"], env=env,
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert "GitHub CLI" in check.stdout
    assert "Docker" in check.stdout
    assert "uv" in check.stdout
    assert "Forge" in check.stdout
    assert "Claude Code" in check.stdout
    assert "Codex" in check.stdout
    assert "Playwright browsers" in check.stdout
    assert "Git\n" not in check.stdout
    assert "Node\n" not in check.stdout
    assert all(line.startswith("Missing: ") for line in check.stdout.splitlines())
    assert not log.exists()

    _stub(bin_dir, "forge", 'echo "forge v1.0.2"')
    old_forge = subprocess.run(["/bin/bash", str(script), "--check"], env=env,
                               capture_output=True, text=True)
    assert "Missing: Forge" in old_forge.stdout
    (bin_dir / "forge").unlink()

    installed = tmp_path / "installed"
    installed.mkdir()
    _stub(installed, "uv", f'echo "uv $*" >> "{log}"\n/bin/cp "{installed / "forge"}" "{bin_dir / "forge"}"')
    _stub(installed, "forge", 'echo "forge v1.1.0"')
    _stub(bin_dir, "brew", f'echo "brew $*" >> "{log}"\n'
          f'case "$*" in *"install uv"*) /bin/cp "{installed / "uv"}" "{bin_dir / "uv"}";; esac')
    _stub(bin_dir, "npm", f'echo "npm $*" >> "{log}"')
    _stub(bin_dir, "npx", f'echo "npx $*" >> "{log}"')
    # A command installed earlier in the run can be called through the same PATH.
    full = subprocess.run(["/bin/bash", str(script)], env=env,
                          capture_output=True, text=True)
    assert full.returncode == 0, full.stderr
    calls = log.read_text().splitlines()
    assert sum("install gh" in call for call in calls) == 1
    assert sum("install --cask docker" in call for call in calls) == 1
    assert sum("install uv" in call for call in calls) == 1
    assert sum("@anthropic-ai/claude-code" in call for call in calls) == 1
    assert sum("@openai/codex" in call for call in calls) == 1
    assert sum("symphony-forge==1.1.0" in call for call in calls) == 1
    assert sum("playwright install" in call for call in calls) == 1
    assert "forge v1.1.0" in full.stdout
    assert "sign in" in full.stdout.lower()


def _windows_check_and_install(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for name in ("git", "node", "winget", "npm", "npx", "wsl"):
        (bin_dir / f"{name}.cmd").write_text("@echo off\n", encoding="utf-8")
    (bin_dir / "wsl.cmd").write_text("@echo Default Version: 2\n", encoding="utf-8")
    powershell = shutil.which("powershell")
    assert powershell
    env = os.environ | {"PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                        "LOCALAPPDATA": str(tmp_path)}
    script = ROOT / "scripts/install-windows.ps1"
    check = subprocess.run([powershell, "-NoProfile", "-File", str(script), "-Check"],
                           env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert "GitHub CLI" in check.stdout and "Forge" in check.stdout
    assert all(line.startswith("Missing: ") for line in check.stdout.splitlines())
    assert not log.exists()
    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "uv.cmd").write_text(
        f'@echo off\necho uv %* >> "{log}"\ncopy /Y "{installed / "forge.cmd"}" "{bin_dir / "forge.cmd"}" >nul\n',
        encoding="utf-8")
    (installed / "forge.cmd").write_text("@echo forge v1.1.0\n", encoding="utf-8")
    (bin_dir / "winget.cmd").write_text(
        f'@echo off\necho winget %* >> "{log}"\n'
        f'echo %* | findstr /C:"astral-sh.uv" >nul && copy /Y "{installed / "uv.cmd"}" "{bin_dir / "uv.cmd"}" >nul\n'
        'exit /b 0\n',
        encoding="utf-8")
    for name in ("npm", "npx"):
        (bin_dir / f"{name}.cmd").write_text(
            f'@echo off\necho {name} %* >> "{log}"\n', encoding="utf-8")
    full = subprocess.run([powershell, "-NoProfile", "-File", str(script)],
                          env=env, capture_output=True, text=True)
    assert full.returncode == 0, full.stderr
    calls = log.read_text().splitlines()
    assert sum("GitHub.cli" in call for call in calls) == 1
    assert sum("Docker.DockerDesktop" in call for call in calls) == 1
    assert sum("symphony-forge==1.1.0" in call for call in calls) == 1
    assert "sign in" in full.stdout.lower()


def test_2_one_install_script_per_laptop_checks_and_installs(tmp_path):
    if os.name == "nt":
        _windows_check_and_install(tmp_path)
    else:
        _mac_check_and_install(tmp_path)
