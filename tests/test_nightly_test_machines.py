"""Nightly tests use the configured test machine.

Test-audit gate:
1. Protect the runner label in the workflow consumed by GitHub after init and sync.
2. Reusing the general runner sends nightly tests to the wrong machine.
3. The PR-machine test requires the old nightly behavior; this owns its replacement.
4. Invoke real commands and read their workflow; no production seam is needed.
"""
import json

from test_groups_pytest import _new_client
from test_testplace_workflow import _jobs

STORY = "FIX-FULL-SUITE-ON-TEST-RUNNER"


def test_1_nightly_tests_use_test_runner_with_runner_as_fallback(repo, gh, tmp_path):
    client = _new_client(repo, gh, tmp_path, "nightly-machines")
    workflow = client / ".github/workflows/forge.yml"
    assert '    runs-on: "ubuntu-24.04"\n' in _jobs(workflow.read_text("utf-8"))["full-suite"]
    repo.git("checkout", "-qb", "fix/nightly-machines", cwd=client)
    settings = client / "forge.toml"
    original = settings.read_text("utf-8")
    for machine in ("fast-tests", "windows-latest", None):
        settings.write_text((f'test_runner = {json.dumps(machine)}\n' if machine else "") + original,
                            encoding="utf-8")
        synced = repo.forge("sync", cwd=client)
        assert synced.returncode == 0, synced.stdout + synced.stderr
        jobs = _jobs(workflow.read_text("utf-8"))
        assert f'    runs-on: {json.dumps(machine or "ubuntu-24.04")}\n' in jobs["full-suite"]
        assert '    runs-on: "ubuntu-24.04"\n' in jobs["full-suite-result"]
