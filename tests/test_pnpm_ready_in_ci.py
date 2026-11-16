"""A pnpm client's generated workflow makes pnpm available before its tests run."""
import json
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

STORY = "FIX-AFTER-THE-UPGRADE-FROM-V1-2-28-TO-V1-2-4"
pytestmark = pytest.mark.platform


def _jobs(workflow):
    return (workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0],
            workflow.split("\n  full-suite:\n")[1].split("\n  full-suite-result:\n")[0])


def test_1_new_pnpm_client_enables_pnpm_before_tests(repo, gh, tmp_path):
    client, result = _fresh_client(repo, gh, tmp_path, "--starter")
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    for job in _jobs(workflow):
        assert "corepack enable" in job
        assert job.index("corepack enable") < job.index("forge test")


def test_2_npm_client_has_no_pnpm_setup(repo):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("checkout", "-qb", "fix/npm")
    current = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8").replace("v1.2.2", current))
    repo.write("package.json", json.dumps({"scripts": {"test": "npm test"}}))
    repo.write("package-lock.json", "{}\n")
    assert repo.forge("sync").returncode == 0
    assert "corepack" not in (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
