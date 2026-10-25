"""Generated Windows client checks allow one retry and retain a second failure."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import ROOT
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

pytestmark = pytest.mark.platform

STORY = "windows-rerun-flakes"


@pytest.mark.parametrize("setup", ["init", "earlier-adoption"])
@pytest.mark.parametrize("command_style", ["powershell", "split-pytest"])
def test_3_windows_client_checks_retry_once(repo, gh, tmp_path, setup, command_style):
    # The Forge test command runs through the repo shell, so preserve its first failure.
    command = 'python retry_probe.py && python -c "print(\'suite passed\')"'
    windows_command = ('pwsh -File "retry probe.ps1"'
                       if command_style == "powershell" else "python -m pytest test_retry_probe.py -q")
    current = repo.forge("--version").stdout.split()[-1]
    if setup == "init":
        config = (f'version = "{current}"\nrepo = "client"\n'
                  f'runner = "windows-latest"\ntest = {json.dumps(windows_command)}\n'
                  'checks = ["tests", "forge-pr-check"]\n')
        client = _new_repo(repo, gh, tmp_path, config)
        if command_style == "split-pytest":
            (client / "requirements.txt").write_text("pytest-split\n", encoding="utf-8")
        result = repo.forge("init", "--actions", "yes", "--runner", "windows-latest", cwd=client)
        assert result.returncode == 0, result.stdout + result.stderr
        repo.git("checkout", "-qb", "fix/windows-client-retries", cwd=client)
    else:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client, dirs_exist_ok=True)
        config = (client / "forge.toml").read_text(encoding="utf-8")
        if command_style == "split-pytest":
            (client / "requirements.txt").write_text("pytest-split\n", encoding="utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt Forge on an earlier release")
        repo.git("push", "-qu", "origin", "main")
        repo.git("checkout", "-qb", "fix/windows-client-retries")
        config = config.replace('version = "v1.2.2"', f'version = "{current}"')
        config = re.sub(r"^test = .+$", lambda _: f"test = {json.dumps(windows_command)}", config, flags=re.M)
        config = 'runner = "windows-latest"\n' + config
        (client / "forge.toml").write_text(config, encoding="utf-8")
        result = repo.forge("sync", cwd=client)
        assert result.returncode == 0, result.stdout + result.stderr
    (client / "retry_probe.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "path = Path(os.environ['ATTEMPT_FILE'])\n"
        "attempt = int(path.read_text(encoding='utf-8')) + 1 if path.exists() else 1\n"
        "path.write_text(str(attempt), encoding='utf-8')\n"
        "assert attempt > int(os.environ['FAILURES']), 'suite assertion failed'\n",
        encoding="utf-8")
    (client / "test_retry_probe.py").write_text(
        "def test_probe():\n" + "".join("    " + line + "\n" for line in
        (client / "retry_probe.py").read_text(encoding="utf-8").splitlines()), encoding="utf-8")
    (client / "retry probe.ps1").write_text(
        "$path = $env:ATTEMPT_FILE\n"
        "$attempt = if (Test-Path $path) { [int](Get-Content $path) + 1 } else { 1 }\n"
        "Set-Content -Path $path -Value $attempt -NoNewline\n"
        "if ($attempt -le [int]$env:FAILURES) {\n"
        "  switch ($env:FAILURE_MODE) {\n"
        "    'exit' { exit 7 }\n"
        "    'throw' { throw 'suite assertion failed' }\n"
        "    'native' { python -c 'import sys; sys.exit(7)'; exit $LASTEXITCODE }\n"
        "  }\n"
        "}\n", encoding="utf-8")
    bash = shutil.which("bash")
    pwsh = shutil.which("pwsh") or str(ROOT / ".venv/powershell/pwsh")
    assert bash, "Linux and Mac checks need Bash"
    if os.name != "nt" and not os.path.isfile(pwsh):
        pytest.skip("Real PowerShell is required; the Windows full suite supplies it")
    assert os.path.isfile(pwsh), "Install real PowerShell to prove Windows client commands"
    # Keep the fixture's Forge launcher and the active Python before system tools.
    test_path = os.pathsep.join([str(repo.bin), str(Path(sys.executable).parent),
                                 str(Path(pwsh).parent), os.environ["PATH"]])
    windows_check = None
    for runner in ("windows-latest", "ubuntu-latest", "macos-latest"):
        repo.git("checkout", "-q", "fix/windows-client-retries", cwd=client)
        settings = config.replace('runner = "windows-latest"', f'runner = "{runner}"')
        if runner != "windows-latest":
            settings = re.sub(r"^test = .+$", lambda _: f"test = {json.dumps(command)}",
                              settings, flags=re.M)
            (client / "forge.toml").write_text(settings, encoding="utf-8")
            synced = repo.forge("sync", cwd=client)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
        tests, check = workflow.split("\n  tests:\n", 1)[1].split("\n  forge-pr-check:\n", 1)
        run = json.loads(re.findall(r"^      - run: (.+)$", tests, re.M)[-1])
        # Actions checks out pull requests detached, without a local Forge item.
        repo.git("checkout", "-q", "--detach", "HEAD", cwd=client)
        if runner == "windows-latest" and command_style == "split-pytest":
            empty_attempts = client / "empty-group-attempts.txt"
            empty = subprocess.run([pwsh, "-NoProfile", "-NonInteractive", "-Command",
                                    run.replace("${{ matrix.group }}", "6")], cwd=client,
                                   capture_output=True, text=True, encoding="utf-8",
                                   env={**os.environ, "ATTEMPT_FILE": empty_attempts.as_posix(),
                                        "FAILURES": "0", "PATH": test_path}, timeout=30)
            assert empty.returncode == 0, empty.stdout + empty.stderr
            assert not empty_attempts.exists(), "An empty group only collects the unsplit suite"
            run = run.replace("${{ matrix.group }}", "1")
        normalized_check = check.replace(runner, "RUNNER")
        if windows_check is None:
            windows_check = normalized_check
        assert normalized_check == windows_check, "The trusted PR gate must keep the same commands"
        assert "        shell: bash\n" not in tests
        if runner != "windows-latest":
            assert run == "forge test --change"
        # Exercise the Actions shell: configured PowerShell scripts use pwsh explicitly,
        # including native failures, throws and script exits.
        modes = (("native", "throw", "exit") if runner == "windows-latest" and
                 command_style == "powershell" else ("native",))
        for mode in modes:
            for failures in (1, 2, 0):
                attempts = client / f"attempts-{runner}-{mode}-{failures}.txt"
                shell = ([pwsh, "-NoProfile", "-NonInteractive", "-Command", run]
                         if runner == "windows-latest" else
                         [bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", run])
                executed = subprocess.run(shell, cwd=client, capture_output=True, text=True,
                                          encoding="utf-8", env={**os.environ,
                                          "PATH": test_path,
                                          "ATTEMPT_FILE": attempts.as_posix(),
                                          "FAILURES": str(failures), "FAILURE_MODE": mode}, timeout=30)
                expected_attempts = 2 if runner == "windows-latest" and failures else 1
                assert attempts.exists(), executed.stdout + executed.stderr
                assert attempts.read_text(encoding="utf-8") == str(expected_attempts), executed.stderr
                passes = failures == 0 or (runner == "windows-latest" and failures == 1)
                assert (executed.returncode == 0) == passes, executed.stdout + executed.stderr
