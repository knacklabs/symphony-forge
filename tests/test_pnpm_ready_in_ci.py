"""After forge sync, a pnpm client's generated workflow sets up pnpm before its tests run."""
import json
import shutil

import pytest

from conftest import ROOT

STORY = "FIX-AFTER-THE-UPGRADE-FROM-V1-2-28-TO-V1-2-4"
pytestmark = pytest.mark.platform


def _sync(repo, files):
    shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    repo.git("checkout", "-qb", "fix/pnpm")
    current = repo.forge("--version").stdout.split()[-1]
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8").replace("v1.2.2", current))
    for name, text in files.items():
        repo.write(name, text)
    # The nested lockfile search lists tracked files only, so stage what the client would commit.
    repo.git("add", "-A")
    result = repo.forge("sync")
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    return (workflow.split("\n  tests:\n")[1].split("\n  forge-pr-check:\n")[0],
            workflow.split("\n  full-suite:\n")[1].split("\n  full-suite-result:\n")[0])


def _assert_setup(job, version):
    assert "pnpm/action-setup@v4" in job
    assert job.index("pnpm/action-setup@v4") < job.index("forge test")
    assert "corepack" not in job
    assert ("version:" in job.split("pnpm/action-setup@v4")[1].split("setup-node")[0]) == bool(version)
    if version:
        assert f"version: {json.dumps(version)}" in job


def test_1_package_manager_field_sets_up_pnpm_without_a_version(repo):
    jobs = _sync(repo, {"package.json": json.dumps({"packageManager": "pnpm@10.20.0"})})
    for job in jobs:
        _assert_setup(job, None)


def test_2_lockfile_under_web_only_sets_up_pnpm_from_lockfile_format(repo):
    jobs = _sync(repo, {"web/pnpm-lock.yaml": "lockfileVersion: '9.0'\n"})
    for job in jobs:
        _assert_setup(job, "10")


def test_5_dev_engines_without_version_reads_nested_lockfile_format(repo):
    dev = {"devEngines": {"packageManager": {"name": "pnpm"}}}
    jobs = _sync(repo, {"package.json": json.dumps(dev), "web/pnpm-lock.yaml": "lockfileVersion: '6.0'\n"})
    for job in jobs:
        _assert_setup(job, "8")


def test_3_engines_pnpm_without_package_manager_passes_that_version(repo):
    jobs = _sync(repo, {"package.json": json.dumps({"engines": {"pnpm": "^10.33.0"}}),
                        "pnpm-lock.yaml": "lockfileVersion: '9.0'\n"})
    for job in jobs:
        _assert_setup(job, "^10.33.0")


def test_4_npm_client_has_no_pnpm_setup(repo):
    jobs = _sync(repo, {"package.json": json.dumps({"scripts": {"test": "npm test"}}),
                        "package-lock.json": "{}\n"})
    for job in jobs:
        assert "pnpm" not in job.replace("pnpm-", "")
