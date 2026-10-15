"""Generated Windows client checks allow one retry and retain a second failure."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess

import pytest

from conftest import ROOT
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "windows-rerun-flakes"


@pytest.mark.parametrize("setup", ["init", "earlier-adoption"])
def test_3_windows_client_checks_retry_once(repo, gh, tmp_path, setup):
    command = 'python retry_probe.py; python -c "print(\'suite passed\')"'
    current = repo.forge("--version").stdout.split()[-1]
    if setup == "init":
        config = (f'version = "{current}"\nrepo = "client"\n'
                  f'runner = "windows-latest"\ntest = {json.dumps(command)}\n'
                  'checks = ["tests", "forge-pr-check"]\n')
        client = _new_repo(repo, gh, tmp_path, config)
        result = repo.forge("init", "--runner", "windows-latest", cwd=client)
    else:
        client = repo.path
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", client, dirs_exist_ok=True)
        config = (client / "forge.toml").read_text(encoding="utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt Forge on an earlier release")
        repo.git("checkout", "-qb", "fix/windows-client-retries")
        config = config.replace('version = "v1.2.2"', f'version = "{current}"')
        config = re.sub(r"^test = .+$", lambda _: f"test = {json.dumps(command)}", config, flags=re.M)
        config = 'runner = "windows-latest"\n' + config
        (client / "forge.toml").write_text(config, encoding="utf-8")
        result = repo.forge("sync", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    if setup == "init":
        repo.git("checkout", "-qb", "fix/windows-client-retries", cwd=client)
    (client / "retry_probe.py").write_text(
        "import os\nfrom pathlib import Path\n"
        "path = Path(os.environ['ATTEMPT_FILE'])\n"
        "attempt = int(path.read_text(encoding='utf-8')) + 1 if path.exists() else 1\n"
        "path.write_text(str(attempt), encoding='utf-8')\n"
        "assert attempt > int(os.environ['FAILURES']), 'suite assertion failed'\n",
        encoding="utf-8")
    bash = shutil.which("bash")
    assert bash, "GitHub's Windows test step needs bash, supplied by Git for Windows"
    windows_check = None
    for runner in ("windows-latest", "ubuntu-latest", "macos-latest"):
        if runner != "windows-latest":
            settings = config.replace('runner = "windows-latest"', f'runner = "{runner}"')
            (client / "forge.toml").write_text(settings, encoding="utf-8")
            synced = repo.forge("sync", cwd=client)
            assert synced.returncode == 0, synced.stdout + synced.stderr
        workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
        tests, check = workflow.split("\n  tests:\n", 1)[1].split("\n  forge-pr-check:\n", 1)
        run = json.loads(re.findall(r"^      - run: (.+)$", tests, re.M)[-1])
        normalized_check = check.replace(runner, "RUNNER")
        if windows_check is None:
            windows_check = normalized_check
        assert normalized_check == windows_check, "The trusted PR gate must keep the same commands"
        if runner == "windows-latest":
            assert "        shell: bash\n" in tests
        else:
            assert run == command
            assert "        shell: bash\n" not in tests
        # The shell owns the retry; the real command only counts attempts and asserts.
        for failures in (1, 2, 0):
            attempts = client / f"attempts-{runner}-{failures}.txt"
            executed = subprocess.run([bash, "--noprofile", "--norc", "-e", "-o", "pipefail", "-c", run],
                                      cwd=client, capture_output=True, text=True, encoding="utf-8",
                                      env={**os.environ, "ATTEMPT_FILE": attempts.as_posix(),
                                           "FAILURES": str(failures)}, timeout=30)
            expected_attempts = 2 if runner == "windows-latest" and failures else 1
            assert attempts.read_text(encoding="utf-8") == str(expected_attempts), executed.stderr
            passes = failures == 0 or (runner == "windows-latest" and failures == 1)
            assert (executed.returncode == 0) == passes, executed.stdout + executed.stderr
