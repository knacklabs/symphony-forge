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
    _stub(bin_dir, "brew", "exit 0")
    env = os.environ | {"PATH": str(bin_dir), "HOME": str(tmp_path)}
    script = ROOT / "scripts/install-mac.sh"

    check = subprocess.run(["/bin/bash", str(script), "--check"], env=env,
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert "GitHub CLI" in check.stdout
    assert "Missing: Git" in check.stdout.splitlines()
    assert "Missing: Node" in check.stdout.splitlines()
    assert "Docker" in check.stdout
    assert "uv" in check.stdout
    assert "Forge" in check.stdout
    assert "Claude Code" in check.stdout
    assert "Codex" in check.stdout
    assert "Playwright browsers" in check.stdout
    assert all(line.startswith("Missing: ") for line in check.stdout.splitlines())
    assert not log.exists()

    _stub(bin_dir, "forge", 'echo "forge v1.0.2"')
    old_forge = subprocess.run(["/bin/bash", str(script), "--check"], env=env,
                               capture_output=True, text=True)
    assert "Missing: Forge" in old_forge.stdout
    (bin_dir / "forge").unlink()

    installed = tmp_path / "installed"
    installed.mkdir()
    for name in ("git", "node"):
        _stub(installed, name, "exit 0")
    _stub(installed, "uv", f'echo "uv $*" >> "{log}"\n'
          f'case "$*" in "tool dir --bin") echo "{bin_dir}";; '
          f'*"tool install"*) /bin/cp "{installed / "forge"}" "{bin_dir / "forge"}";; esac')
    _stub(installed, "forge", 'echo "forge v1.1.0"')
    _stub(bin_dir, "brew", f'echo "brew $*" >> "{log}"\n'
          f'case "$2" in git|node|uv) /bin/cp "{installed}/$2" "{bin_dir}/$2";; esac')
    _stub(bin_dir, "npm", f'echo "npm $*" >> "{log}"')
    _stub(bin_dir, "npx", f'echo "npx $*" >> "{log}"')
    # A command installed earlier in the run can be called through the same PATH.
    full = subprocess.run(["/bin/bash", str(script)], env=env,
                          capture_output=True, text=True)
    assert full.returncode == 0, full.stderr
    calls = log.read_text().splitlines()
    assert calls == ["brew install git", "brew install gh", "brew install node",
                     "brew install --cask docker", "brew install uv",
                     "uv tool install --force git+https://github.com/knacklabs/symphony-forge@v1.1.0", "uv tool update-shell",
                     "uv tool dir --bin", "npm install -g @anthropic-ai/claude-code",
                     "npm install -g @openai/codex",
                     "npx --yes playwright install chromium firefox webkit"]
    assert "forge v1.1.0" in full.stdout
    assert "sign in" in full.stdout.lower()
    assert "new terminal" in full.stdout.lower()


def _mac_homebrew_authorization_and_ready_tools(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    env = os.environ | {"PATH": str(bin_dir), "HOME": str(tmp_path)}
    script = ROOT / "scripts/install-mac.sh"
    _stub(bin_dir, "curl", f'echo "curl $*" >> "{log}"\necho "exit 23"')
    _stub(tmp_path, "brew", f'echo "brew $*" >> "{log}"')
    _stub(bin_dir, "sudo", f'echo "sudo $*" >> "{log}"\nexit 1')
    failed = subprocess.run(["/bin/bash"], input=script.read_text(), env=env,
                            capture_output=True, text=True)
    assert failed.returncode != 0
    assert "administrator" in (failed.stdout + failed.stderr).lower()
    assert log.read_text().splitlines() == ["sudo -v"]

    _stub(bin_dir, "sudo", f'echo "sudo $*" >> "{log}"')
    _stub(bin_dir, "curl", f'echo "curl $*" >> "{log}"\nexit 22')
    offline = subprocess.run(["/bin/bash"], input=script.read_text(), env=env,
                             capture_output=True, text=True)
    assert offline.returncode == 1
    assert "Homebrew could not be downloaded" in offline.stderr
    assert "run this script again" in offline.stderr
    log.unlink()
    _stub(bin_dir, "curl", f'echo "curl $*" >> "{log}"\n'
          f'echo "/bin/cp {tmp_path / "brew"} {bin_dir / "brew"}"')
    _stub(bin_dir, "git", "exit 0")
    _stub(bin_dir, "gh", "exit 0")
    _stub(bin_dir, "node", "exit 0")
    _stub(bin_dir, "docker", "exit 0")
    _stub(bin_dir, "uv", "exit 0")
    _stub(bin_dir, "claude", "exit 0")
    _stub(bin_dir, "codex", "exit 0")
    _stub(bin_dir, "forge", 'echo "forge v1.1.0"')
    for kind in ("chromium", "firefox", "webkit"):
        (tmp_path / "Library/Caches/ms-playwright" / f"{kind}-1").mkdir(parents=True)
    check = subprocess.run(["/bin/bash", str(script), "--check"], env=env,
                           capture_output=True, text=True)
    assert check.returncode == 0 and check.stdout == "Missing: Homebrew\n"
    full = subprocess.run(["/bin/bash"], input=script.read_text(), env=env,
                          capture_output=True, text=True)
    assert full.returncode == 0, full.stderr
    assert log.read_text().splitlines() == ["sudo -v",
                                           "curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh"]
    assert "forge v1.1.0" in full.stdout


def _windows_check_and_install(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    for name in ("winget", "npm", "npx", "wsl"):
        (bin_dir / f"{name}.cmd").write_text("@echo off\n", encoding="utf-8")
    (bin_dir / "wsl.cmd").write_text("@echo Default Version: 2\n", encoding="utf-8")
    powershell = shutil.which("powershell")
    assert powershell
    system_root = Path(os.environ["SystemRoot"])
    system_path = os.pathsep.join(str(system_root / part) for part in ("System32", "", "System32/WindowsPowerShell/v1.0"))
    env = os.environ | {"PATH": str(bin_dir) + os.pathsep + system_path,
                        "PATHEXT": ".CMD;.BAT", "LOCALAPPDATA": str(tmp_path),
                        "UV_TOOL_BIN_DIR": str(tmp_path / "tools")}
    script = ROOT / "scripts/install-windows.ps1"
    check = subprocess.run([powershell, "-NoProfile", "-File", str(script), "-Check"],
                           env=env, capture_output=True, text=True)
    assert check.returncode == 0, check.stderr
    assert set(check.stdout.splitlines()) == {
        "Missing: Git", "Missing: GitHub CLI", "Missing: Node", "Missing: Docker",
        "Missing: uv", "Missing: Forge",
        "Missing: Claude Code", "Missing: Codex", "Missing: Playwright browsers"}
    assert all(line.startswith("Missing: ") for line in check.stdout.splitlines())
    assert not log.exists()
    installed = tmp_path / "installed"
    installed.mkdir()
    tool_bin = tmp_path / "tools"
    tool_bin.mkdir()
    (installed / "uv.cmd").write_text(
        f'@echo off\necho uv %* >> "{log}"\n'
        f'if "%1 %2 %3"=="tool dir --bin" echo {tool_bin}\n'
        f'if "%1 %2"=="tool install" copy /Y "{installed / "forge.cmd"}" "{tool_bin / "forge.cmd"}" >nul\n',
        encoding="utf-8")
    (installed / "forge.cmd").write_text("@echo forge v1.1.0\n", encoding="utf-8")
    for name in ("git", "node"):
        (installed / f"{name}.cmd").write_text("@echo off\n", encoding="utf-8")
    for name in ("claude", "codex"):
        (installed / f"{name}.cmd").write_text(f"@echo {name} ready\n", encoding="utf-8")
        (installed / f"{name}.ps1").write_text("throw 'PowerShell blocked this shim'\n", encoding="utf-8")
    (bin_dir / "winget.cmd").write_text(
        f'@echo off\necho winget %* >> "{log}"\n'
        f'echo %* | findstr.exe /C:"Git.Git" >nul && copy /Y "{installed / "git.cmd"}" "{bin_dir / "git.cmd"}" >nul\n'
        f'echo %* | findstr.exe /C:"GitHub.cli" >nul && copy /Y "{installed / "gh.cmd"}" "{bin_dir / "gh.cmd"}" >nul\n'
        f'echo %* | findstr.exe /C:"OpenJS.NodeJS.LTS" >nul && copy /Y "{installed / "node.cmd"}" "{bin_dir / "node.cmd"}" >nul\n'
        f'echo %* | findstr.exe /C:"astral-sh.uv" >nul && copy /Y "{installed / "uv.cmd"}" "{bin_dir / "uv.cmd"}" >nul\n'
        f'echo %* | findstr.exe /C:"Docker.DockerDesktop" >nul && copy /Y "{installed / "docker.cmd"}" "{bin_dir / "docker.cmd"}" >nul\n'
        'exit /b 0\n',
        encoding="utf-8")
    for name in ("gh", "docker"):
        (installed / f"{name}.cmd").write_text("@echo off\n", encoding="utf-8")
    for name in ("npm", "npx"):
        (bin_dir / f"{name}.cmd").write_text(
            f'@echo off\necho {name} %* >> "{log}"\n'
            + (f'echo %* | findstr.exe /C:"@anthropic-ai/claude-code" >nul && '
               f'copy /Y "{installed / "claude.cmd"}" "{bin_dir / "claude.cmd"}" >nul\n'
               f'echo %* | findstr.exe /C:"@anthropic-ai/claude-code" >nul && '
               f'copy /Y "{installed / "claude.ps1"}" "{bin_dir / "claude.ps1"}" >nul\n'
               f'echo %* | findstr.exe /C:"@openai/codex" >nul && '
               f'copy /Y "{installed / "codex.cmd"}" "{bin_dir / "codex.cmd"}" >nul\n'
               f'echo %* | findstr.exe /C:"@openai/codex" >nul && '
               f'copy /Y "{installed / "codex.ps1"}" "{bin_dir / "codex.ps1"}" >nul\n'
               'exit /b 0\n'
               if name == "npm" else ""), encoding="utf-8")
        (bin_dir / f"{name}.ps1").write_text("throw 'Use the .cmd installer'\n", encoding="utf-8")
    piped = ("function Invoke-RestMethod { param($Uri) "
             f"Get-Content -Raw -LiteralPath '{script}' }}; "
             "irm https://example.invalid/install-windows.ps1 | iex")
    full = subprocess.run([powershell, "-NoProfile", "-Command", piped],
                          env=env, capture_output=True, text=True)
    assert full.returncode == 0, full.stderr
    calls = [line.rstrip() for line in log.read_text().splitlines()]
    assert calls == [
        "winget install --id Git.Git --exact --source winget --accept-package-agreements --accept-source-agreements",
        "winget install --id GitHub.cli --exact --source winget --accept-package-agreements --accept-source-agreements",
        "winget install --id OpenJS.NodeJS.LTS --exact --source winget --accept-package-agreements --accept-source-agreements",
        "winget install --id astral-sh.uv --exact --source winget --accept-package-agreements --accept-source-agreements",
        "winget install --id Docker.DockerDesktop --exact --source winget --accept-package-agreements --accept-source-agreements",
        "uv tool install --force git+https://github.com/knacklabs/symphony-forge@v1.1.0",
        "uv tool update-shell", "uv tool dir --bin",
        "npm install -g @anthropic-ai/claude-code", "npm install -g @openai/codex",
        "npx --yes playwright install chromium firefox webkit"]
    assert "forge v1.1.0" in full.stdout
    assert "sign in" in full.stdout.lower()
    assert "claude.cmd" in full.stdout and "codex.cmd" in full.stdout
    assert "new powershell window" in full.stdout.lower()
    agents = subprocess.run([powershell, "-NoProfile", "-ExecutionPolicy", "Restricted",
                             "-Command", "& claude.cmd; & codex.cmd"], env=env,
                            capture_output=True, text=True)
    assert agents.returncode == 0, agents.stderr
    assert agents.stdout.splitlines() == ["claude ready", "codex ready"]


def _windows_wsl2_restart_and_all_present(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "calls"
    system_root = Path(os.environ["SystemRoot"])
    env = os.environ | {"PATH": str(bin_dir) + os.pathsep + str(system_root / "System32"),
                        "PATHEXT": ".CMD;.BAT", "LOCALAPPDATA": str(tmp_path)}
    for name in ("git", "gh", "node", "docker", "uv", "claude", "codex"):
        (bin_dir / f"{name}.cmd").write_text("@echo off\n", encoding="utf-8")
    for name in ("winget", "npm", "npx"):
        (bin_dir / f"{name}.cmd").write_text(
            f'@echo off\necho {name} %* >> "{log}"\n', encoding="utf-8")
    (bin_dir / "forge.cmd").write_text("@echo forge v1.1.0\n", encoding="utf-8")
    for kind in ("chromium", "firefox", "webkit"):
        (tmp_path / "ms-playwright" / f"{kind}-1").mkdir(parents=True)
    (bin_dir / "wsl.cmd").write_text("@echo Default Version: 2\n", encoding="utf-8")
    script = ROOT / "scripts/install-windows.ps1"
    powershell = shutil.which("powershell")
    check = subprocess.run([powershell, "-NoProfile", "-File", str(script), "-Check"],
                           env=env, capture_output=True, text=True)
    assert check.returncode == 0 and check.stdout.strip() == ""
    full = subprocess.run([powershell, "-NoProfile", "-File", str(script)],
                          env=env, capture_output=True, text=True)
    assert full.returncode == 0 and "forge v1.1.0" in full.stdout
    assert not log.exists()
    # wsl.exe exists on a fresh laptop but fails on --status with its message on stderr.
    (bin_dir / "wsl.cmd").write_text(
        '@echo off\nif "%1"=="--install" (echo WSL install requested& exit /b 0)\n'
        'echo WSL is not installed. Run wsl --install. 1>&2\nexit /b 1\n', encoding="utf-8")
    missing = subprocess.run([powershell, "-NoProfile", "-File", str(script), "-Check"],
                             env=env, capture_output=True, text=True)
    assert missing.returncode == 0 and missing.stdout.strip() == "Missing: WSL2 for Docker"
    # The runner's own rights never decide the path: the script reads FORGE_INSTALL_ADMIN first.
    user = subprocess.run([powershell, "-NoProfile", "-File", str(script)],
                          env=env | {"FORGE_INSTALL_ADMIN": "0"}, capture_output=True, text=True)
    assert user.returncode == 1
    assert "Open PowerShell as administrator" in user.stdout
    assert "restart" in user.stdout.lower()
    assert "WSL install requested" not in user.stdout
    admin = env | {"FORGE_INSTALL_ADMIN": "1"}
    setup = subprocess.run([powershell, "-NoProfile", "-File", str(script)],
                           env=admin, capture_output=True, text=True)
    assert setup.returncode == 0, setup.stderr
    assert "WSL install requested" in setup.stdout
    assert "restart" in setup.stdout.lower()

    # An installed WSL1 needs the Virtual Machine Platform feature, then a version change.
    (bin_dir / "wsl.cmd").write_text(
        f'@echo off\nif "%1"=="--status" (echo Default Version: 1) else (echo wsl %* >> "{log}")\n',
        encoding="utf-8")
    (bin_dir / "dism.cmd").write_text(
        f'@echo off\necho dism %* >> "{log}"\nexit /b 3010\n', encoding="utf-8")
    wsl1_check = subprocess.run([powershell, "-NoProfile", "-File", str(script), "-Check"],
                                env=env, capture_output=True, text=True)
    assert wsl1_check.returncode == 0
    assert wsl1_check.stdout.strip() == "Missing: WSL2 for Docker"
    assert not log.exists()
    wsl1_setup = subprocess.run([powershell, "-NoProfile", "-File", str(script)],
                                env=admin, capture_output=True, text=True)
    assert wsl1_setup.returncode == 0, wsl1_setup.stderr
    assert "Windows asks for a restart" in wsl1_setup.stdout
    assert [line.rstrip() for line in log.read_text().splitlines()] == [
        "dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart",
        "wsl --set-default-version 2"]

def test_2_one_install_script_per_laptop_checks_and_installs(tmp_path):
    if os.name == "nt":
        _windows_check_and_install(tmp_path)
        wsl_dir = tmp_path / "wsl"
        wsl_dir.mkdir()
        _windows_wsl2_restart_and_all_present(wsl_dir)
    else:
        _mac_check_and_install(tmp_path)
        brew_dir = tmp_path / "homebrew"
        brew_dir.mkdir()
        _mac_homebrew_authorization_and_ready_tools(brew_dir)
