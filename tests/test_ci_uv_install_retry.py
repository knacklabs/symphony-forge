"""The generated Actions contract retries uv installation once.

Test-audit gate: protect automatic recovery and a final failed install at the generated
workflow boundary. Omitting the retry or allowing its error breaks this contract.
Existing bootstrap tests only check tool presence. These command tests need no new seam.
"""
import re
import shutil

from conftest import ROOT
from test_fix_new_repos_get_claude_as_their_worker_by import _new_repo

STORY = "FIX-UV-SETUP-RETRY"


def _assert_retry(client):
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    jobs = re.split(r"^  [\w-]+:\n", workflow, flags=re.M)[1:]
    installs = 0
    for job in jobs:
        steps = re.split(r"^      - ", job, flags=re.M)[1:]
        for index, step in enumerate(steps):
            if "uses: astral-sh/setup-uv@" not in step or "continue-on-error: true" not in step:
                continue
            installs += 1
            step_id = re.search(r"^        id: ([\w-]+)$", step, re.M)[1]
            retry = steps[index + 1]
            assert "uses: astral-sh/setup-uv@v6" in retry
            assert f"if: steps.{step_id}.outcome == 'failure'" in retry
            assert "continue-on-error:" not in retry
            assert "enable-cache: true" in step and "enable-cache: true" in retry
        assert sum("uses: astral-sh/setup-uv@" in step for step in steps) in (0, 2)
    assert installs == 3  # Pull request tests, trusted review and the nightly full suite.


def test_1_new_repo_retries_uv_install_once(repo, gh, tmp_path):
    client = _new_repo(repo, gh, tmp_path)
    result = repo.forge("init", "--actions", "yes", cwd=client)
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_retry(client)


def test_2_earlier_adopted_repo_gets_uv_retry_on_sync(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Adopt an earlier Forge release")
    repo.git("checkout", "-qb", "fix/retry-uv")
    config = (repo.path / "forge.toml").read_text("utf-8")
    version = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
    result = repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    _assert_retry(repo.path)
