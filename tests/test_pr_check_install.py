"""In Forge's own repo the pull request check installs Forge from the base checkout."""
from __future__ import annotations

import pytest

from test_setup import _on_a_branch_with_forge_toml

STORY = "FIX-PR-CHECK-INSTALL"


@pytest.mark.parametrize("repo_line, install", [
    ('repo = "forge-source"\n', "uv tool install ."),
    ("", "uv tool install git+https://github.com/knacklabs/symphony-forge@v"),
])
def test_1_sync_installs_forge_for_pr_check_by_repo_kind(repo, repo_line, install):
    _on_a_branch_with_forge_toml(repo)
    repo.write("forge.toml", (repo.path / "forge.toml").read_text("utf-8") + repo_line)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "config")
    assert repo.forge("sync").returncode == 0
    workflow = (repo.path / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    check_job = workflow.split("\n  forge-pr-check:\n")[1]
    assert f"- run: {install}" in check_job
    if repo_line:
        assert "symphony-forge@" not in check_job
