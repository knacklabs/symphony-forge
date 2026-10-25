"""Generated CI uses Forge's related-test command only when CI owns change tests.

Test-audit gate:
1. Protects the generated workflow contract and doctor's acceptance of that workflow.
2. A regression can make CI run the repo's whole test command, keep tests jobs in local mode,
   or make doctor reject the generated command.
3. Existing tests cover the old full-command workflow and six-group CI, but not test-place-aware
   generation or doctor's new command check.
4. These tests use init, sync and doctor at their command boundaries; no production seam is needed.
"""
from __future__ import annotations

import re
import tomllib

import pytest

from test_setup import _fresh_client

MISSING_TEST_STEP = "does not run forge test --change"


def _jobs(workflow: str) -> dict[str, str]:
    return dict(re.findall(r"^  ([\w-]+):\n(.*?)(?=^  [\w-]+:\n|\Z)", workflow, re.M | re.S))


@pytest.mark.platform
def test_1_ci_workflow_installs_the_pin_and_runs_change_tests(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr

    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    tests_job = _jobs(workflow)["tests"]
    version = tomllib.loads((client / "forge.toml").read_text(encoding="utf-8"))["version"]
    assert tests_job.count('run: "forge test --change"') == 1
    assert f"uv tool install git+https://github.com/knacklabs/symphony-forge@{version}" in tests_job
    assert "--splits" not in tests_job

    doctor = repo.forge("doctor", cwd=client)
    assert MISSING_TEST_STEP not in doctor.stdout


@pytest.mark.platform
def test_2_local_workflow_has_no_test_jobs_even_with_a_tests_check(repo, gh, tmp_path):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    toml = client / "forge.toml"
    config = toml.read_text(encoding="utf-8")
    assert 'test_place = "ci"' in config and 'checks = ["tests", "forge-pr-check"]' in config
    toml.write_text(config.replace('test_place = "ci"', 'test_place = "local"'), encoding="utf-8")

    synced = repo.forge("sync", cwd=client)

    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    names = _jobs(workflow)
    assert "tests" not in names and "tests-passed" not in names and "docs-check" not in names
    assert "forge-pr-check" in names
