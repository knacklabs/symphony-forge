"""Adoption review guidance reaches new and earlier-adopted clients.

Test-audit: the delivered prompt is the contract. Omitting checks that read
shared inputs makes selected tests miss failures. Existing setup tests check
file delivery, not this instruction. The Claude driver records the real brief
without deciding its content. No production seam is needed.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client
from test_worker import calls, install_claude

STORY = "FIX-ADOPTION-SETS-WHOLE-REPO-CHECKS"


@pytest.mark.parametrize("previous", [False, True], ids=["new-client", "previous-adoption"])
def test_1_adoption_review_keeps_shared_input_checks(repo, gh, tmp_path, previous):
    if previous:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        version = repo.forge("--version").stdout.split()[-1]
        config = (repo.path / "forge.toml").read_text(encoding="utf-8")
        repo.write("forge.toml", config.replace('version = "v1.2.2"', f'version = "{version}"'))
        repo.git("switch", "-q", "-c", "fix/adoption-guidance")
        result = repo.forge("sync")
    else:
        client, result = _fresh_client(repo, gh, tmp_path)
        repo.path = client
    assert result.returncode == 0, result.stdout + result.stderr
    for host in (".codex", ".claude"):
        guide = " ".join((repo.path / host / "skills/forge/SKILL.md").read_text(
            encoding="utf-8").split())
        assert ("During adoption review, name the repo's cheap whole-repo checks that read shared "
                "files without imports, such as rule checks, file inventories and configuration "
                "checks: changed-only selection can miss them.") in guide
        assert ("checks: changed-only selection can miss them. Include their pytest files or "
                "node IDs in Python `always_test`, or their commands "
                "beside changed-test selection in TypeScript `fast_test`, through the normal "
                "settings fix after the human agrees.") in guide

    if not previous:
        repo.git("switch", "-q", "-c", "fix/adoption-guidance")
    config = (repo.path / "forge.toml").read_text(encoding="utf-8")
    repo.write("forge.toml", config.replace('workers = "codex"', 'workers = "claude"').replace(
        'workers = "split"', 'workers = "claude"'))
    repo.git("add", "-A")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "commit", "-q", "-m",
             "Set up adoption guidance")
    repo.git("switch", "-q", "main")
    repo.git("merge", "-q", "--ff-only", "fix/adoption-guidance")
    repo.git("-c", f"core.hooksPath={tmp_path / 'no-hooks'}", "push", "-q", "origin", "main")
    log = install_claude(repo)
    started = repo.forge("fix", "start", "Check adoption guidance", "--done",
                         "Adoption review names shared-input checks", "--kind", "mechanical")
    assert started.returncode == 0, started.stdout + started.stderr
    worked = repo.forge("work", "check-adoption-guidance")
    assert worked.returncode == 0, worked.stdout + worked.stderr
    brief = " ".join(calls(log)[-1]["brief"].split())
    assert ("During adoption review, name cheap whole-repo checks that read shared files without "
            "imports, such as rule checks, file inventories and configuration checks.") in brief
    assert ("Changed-only selection can miss them. Report their pytest files or node IDs "
            "for Python `always_test`, or their commands "
            "for TypeScript `fast_test` beside changed-test selection, through the normal "
            "settings fix with the owner's agreement.") in brief
    assert "Workers never edit `forge.toml`; give the coordinator the list." in brief
