"""Unsplit CI groups warn without blocking doctor or workflow generation.

Audit: init/sync and doctor own this public configuration contract. Existing
group tests cover sharding, not advice for repeated suites. Removing either
warning or treating it as a problem breaks this test. GitHub alone is faked;
no production seam is added. The workflow is a shipped execution contract.
"""
import json
import re

import pytest

from test_node_test_worker_budget import client
from test_setup import _autoreview

STORY = "FIX-UNSPLIT-GROUPS-WARNING"
WARNING = ("Each CI group runs the same tests because the test command has no {group} placeholder. "
           "Set groups to 1 or add the runner's shard options with {group} and {groups}.")


@pytest.mark.platform
@pytest.mark.parametrize("upgrade,groups,command,split_dependency,warns", [
    (False, 3, "npm test", False, True),
    (True, 3, "npm test", False, True),
    (False, 1, "npm test", False, False),
    (False, 3, "vitest run --shard={group}/{groups}", False, False),
    (False, 3, "pytest tests", True, False),
    (False, 3, "pytest tests", False, True),
    (False, 3, "npm test -- --total={groups}", False, True),
])
def test_1_unsplit_groups_warn_without_refusal(repo, gh, monkeypatch, tmp_path,
                                             upgrade, groups, command, split_dependency, warns):
    client(repo, gh, upgrade)
    repo.git("checkout", "-qb", "fix/group-warning")
    repo.write(".factory/fixes/group-warning.json", json.dumps({
        "kind": "fix", "branch": "fix/group-warning", "why": "Warn about repeated tests",
        "done_when": "Unsplit groups warn", "status": "started"}))
    settings = (repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^(test|fast_test|groups|tools|workers) = .*\n", "", settings, flags=re.M)
    repo.write("forge.toml", f"groups = {groups}\ntest = {json.dumps(command)}\n"
               'tools = "claude"\nworkers = "claude"\n' + settings)
    if split_dependency:
        repo.write("requirements-dev.txt", "pytest-split\n")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    assert workflow.count("::warning::" + WARNING) == int(warns)
    # The advice must not reduce the chosen groups or replace the test command.
    assert f"group: {list(range(1, groups + 1))}" in workflow
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure client test groups")
    gh.respond("auth", "status")
    gh.respond("api", "repos/{owner}/{repo}/branches/main/protection",
               stdout=json.dumps({"required_status_checks": {"contexts": ["tests", "forge-pr-check"]}}))
    _autoreview(tmp_path, monkeypatch)
    checked = repo.forge("doctor")
    assert checked.stdout.count("- Warning: " + WARNING) == int(warns)
    assert checked.returncode == 0, checked.stdout + checked.stderr
