"""Adoption review guidance reaches new and earlier-adopted clients.

Test-audit: the delivered prompt is the contract. Omitting checks that read
shared inputs makes selected tests miss failures. Existing setup tests check
file delivery, not this instruction. No production seam or model fake is needed.
"""
import shutil

import pytest

from conftest import ROOT
from test_setup import _fresh_client

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
        for phrase in ("cheap whole-repo checks", "read shared files without imports",
                       "Python `always_test`", "TypeScript `fast_test`", "normal settings fix"):
            assert phrase in guide, phrase
    brief = " ".join((ROOT / "src/forge/templates/brief.md").read_text(encoding="utf-8").split())
    for phrase in ("cheap whole-repo checks", "Python `always_test`",
                   "TypeScript `fast_test`", "normal settings fix"):
        assert phrase in brief, phrase
