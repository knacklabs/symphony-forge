"""Workflow settings retire superseded PR runs without cancelling other work.

This is the configuration contract consumed by GitHub, checked on shipped output.
Previously workflows queued every commit without retiring the replaced run.
"""
import re
import shutil
import subprocess
import sys

import pytest

from conftest import FORGE_SHIM, ROOT, _install
from test_setup import _fresh_client, _version

STORY = "FIX-CI-CANCEL-SUPERSEDED"


def _assert_pr_concurrency(workflow):
    # Workflow and event isolate different workflows and tests from pr-check.
    # The PR number stays stable across commits; run_id keeps every non-PR run
    # independent, including queued default-branch and manual runs.
    block = re.search(r"^concurrency:\n((?:  .+\n)+)", workflow, re.M)
    assert block, "Missing workflow-level concurrency"
    settings = dict(line.strip().split(": ", 1) for line in block[1].splitlines())
    assert settings["group"] == (
        "${{ github.workflow }}-${{ github.event_name }}-"
        "${{ github.event.pull_request.number || github.run_id }}")
    assert settings["cancel-in-progress"] == (
        "${{ github.event_name == 'pull_request' || "
        "github.event_name == 'pull_request_target' }}")


@pytest.mark.parametrize("name", ["forge-next", "forge", "codex-smoke"])
def test_1_own_workflows_cancel_only_superseded_runs_of_the_same_pr_and_event(name):
    _assert_pr_concurrency((ROOT / f".github/workflows/{name}.yml").read_text("utf-8"))


@pytest.mark.parametrize("adoption", ["new", "v1.2.2"])
def test_2_init_and_previous_release_sync_ship_pr_concurrency(repo, gh, tmp_path, adoption):
    if adoption == "new":
        client, done = _fresh_client(repo, gh, tmp_path)
    else:
        # Generate the old workflow with the actual release's command from its
        # plain-text fixture, then sync with today's release.
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        repo.git("add", "-A")
        repo.git("commit", "-q", "-m", "Adopt the earlier release")
        repo.git("checkout", "-q", "-b", "fix/upgrade-ci")
        old = tmp_path / "old-release"
        shutil.copytree(ROOT / "tests/fixtures/forge-v1.2.2", old)
        (old / "src/forge/cli-py.txt").rename(old / "src/forge/cli.py")
        _install(repo.bin, "old-forge", FORGE_SHIM.format(
            python=sys.executable, src=str(old / "src")))
        previous = subprocess.run([sys.executable, str(repo.bin / "old-forge"), "sync"],
                                  cwd=repo.path, capture_output=True, text=True, timeout=60)
        assert previous.returncode == 0, previous.stdout + previous.stderr
        assert "concurrency:" not in (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
        config = (repo.path / "forge.toml").read_text("utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"',
                                               f'version = "{_version(repo)}"'))
        client, done = repo.path, repo.forge("sync")
    assert done.returncode == 0, done.stdout + done.stderr
    _assert_pr_concurrency((client / ".github/workflows/forge.yml").read_text("utf-8"))
