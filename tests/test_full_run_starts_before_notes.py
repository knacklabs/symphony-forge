"""Init and upgrade deliver the early full-run instructions.

The guide is the agent's public contract: a missing dispatch instruction leaves
proof until tag push. Existing full-run tests own the proof gate, not when the
agent starts it. Real init/sync delivery needs no production test seam.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client, _version

STORY = "start-full-run-early"


@pytest.mark.parametrize("previous, mode", [(False, "ci"), (False, "local"), (True, "local")],
                         ids=["new-ci", "new-local", "previous-adoption-local"])
def test_1_full_run_starts_after_last_product_merge_before_notes(repo, gh, tmp_path, previous, mode):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
        repo.git("checkout", "-q", "-b", "fix/full-run-guide")
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", f'test_place = "{mode}"\n' + config.replace(
            'version = "v1.2.2"', f'version = "{_version(repo)}"'))
        client, result = repo.path, repo.forge("sync")
    else:
        client, result = _fresh_client(repo, gh, tmp_path, "--actions", "yes" if mode == "ci" else "no")
    assert result.returncode == 0, result.stdout + result.stderr
    workflow = (client / ".github/workflows/forge.yml").read_text(encoding="utf-8")
    assert ("workflow_dispatch:" in workflow) == (mode == "ci")
    for host in (".codex", ".claude"):
        path = client / host / "skills/forge/SKILL.md"
        guide = " ".join(path.read_text(encoding="utf-8").split())
        assert "After the last product merge for a release or sign-off, start the full run at once" in guide
        assert "gh workflow run forge.yml --ref <default>" in guide
        assert ("Prepare the release or sign-off notes while it runs, then follow that same run with "
                "`gh run watch <run-id> --exit-status`") in guide
        local = guide.split("Local mode has no scheduled job;", 1)[1].split(
            "A green full run on the latest", 1)[0]
        assert "after the last product merge for a release or sign-off" in local
        assert "start `forge test --full` at once in the main checkout" in local
        assert "Prepare notes while it runs and wait for that same command to finish" in local
        assert "A green full run on the latest default-branch commit is required before pushing a release tag" in guide
