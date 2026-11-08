"""Sync keeps unsplittable client tests in one job.

Audit: the shipped workflow is the contract. Extra gates or repeated groups
break it. Existing coverage expects the old shape. No production seam is needed.
"""
import re

import pytest

from test_node_test_worker_budget import client
from test_fix_gate_on_split_checks import jobs

STORY = "FIX-SIMPLER-CLIENT-CI"


@pytest.mark.platform
@pytest.mark.parametrize("upgrade", [False, True])
@pytest.mark.parametrize("count", [1, 3])
def test_1_unsplittable_client_uses_one_tests_job(repo, gh, upgrade, count):
    client(repo, gh, upgrade)
    repo.git("checkout", "-qb", "fix/single-tests")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^(test|fast_test|groups) = .*\n", "", settings, flags=re.M)
    repo.write("forge.toml", f'groups = {count}\ntest = "npm test"\n' + settings)
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    found = jobs((repo.path / ".github/workflows/forge.yml").read_text("utf-8"))
    assert "docs-check" not in found and "tests-passed" not in found
    test = found["tests"]
    assert "&& 'tests' || 'tests (other event)'" in test
    assert "strategy:" not in test and "needs:" not in test
    assert "run: python .forge/review-tests.py" in test
    assert "if: steps.parent-tests.outputs.reuse != 'true'" in test
    assert 'run: "forge test --change"' in test
    assert "FORGE_GROUPS: '1'" in test
    assert ("::warning::" in test) == (count > 1)
    assert "group: [1]" in found["full-suite"]
