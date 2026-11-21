"""Automatic tests run on pull requests and nightly events; manual full runs stay.

Audit: sync is the public delivery boundary. A restored push trigger repeats
tests after merges. Existing workflow cases protected the opposite contract.
Only GitHub setup is faked; no production seam is needed.
"""
import re

import pytest

from test_setup import _fresh_client
from test_testplace_workflow import _jobs

STORY = "fewer-main-runs"
pytestmark = pytest.mark.platform


@pytest.mark.parametrize("groups", [1, 3])
def test_1_sync_keeps_automatic_main_tests_only_in_the_nightly_run(repo, gh, tmp_path, groups):
    client, initialized = _fresh_client(repo, gh, tmp_path)
    assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    repo.git("switch", "-q", "-c", "fix/main-tests", cwd=client)
    config_path = client / "forge.toml"
    config = re.sub(r"(?m)^(groups|test|fast_test)\s*=.*\n", "",
                    config_path.read_text("utf-8"))
    config_path.write_text(
        f'groups = {groups}\ntest = "python -m pytest tests -q --splits {{groups}} --group {{group}}"\n'
        + config, encoding="utf-8")
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    assert not re.search(r"(?m)^  push:", workflow)
    assert "FORGE_PUSH_BASE" not in workflow
    jobs = _jobs(workflow)
    assert "github.event_name == 'push'" not in jobs["tests"]
    assert "github.event_name == 'schedule'" in jobs["full-suite"]
    assert "github.event_name == 'workflow_dispatch'" in jobs["full-suite"]
    assert "  workflow_dispatch:" in workflow
    assert "forge test --full" in jobs["full-suite"]
    assert "github.event_name == 'pull_request'" in jobs["tests"]
