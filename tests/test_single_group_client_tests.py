"""Sync keeps unsplittable client tests in one job.

Audit: the shipped workflow is the contract. Extra gates or repeated groups
break it. Existing coverage expects the old shape. No production seam is needed.
"""
import json
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
    repo.write("forge.toml", f'groups = {count}\ntest = "npm test"\nfast_test = "npm test"\n' + settings)
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


@pytest.mark.platform
@pytest.mark.parametrize("upgrade,full_split,fast_split", [
    (False, True, False), (False, False, True), (True, True, False),
])
def test_2_pr_and_full_runs_split_their_own_commands(repo, gh, monkeypatch, upgrade,
                                                   full_split, fast_split):
    # Audit: separate commands can need different groups. Prior proofs removed
    # fast_test, so they missed repeated PR tests and lost PR parallelism.
    # Real pytest executes the generated commands; no new production seam is needed.
    client(repo, gh, upgrade)
    repo.git("checkout", "-qb", "fix/separate-test-groups")
    repo.write(".factory/fixes/separate-test-groups.json", json.dumps({
        "kind": "fix", "branch": "fix/separate-test-groups", "status": "started",
        "why": "Configure client tests", "done_when": "Configure forge.toml"}))
    settings = (repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^(test|fast_test|groups) = .*\n", "", settings, flags=re.M)
    plain = "python -m pytest tests -q"
    split = plain + " --splits {groups} --group {group}"
    repo.write("forge.toml", 'groups = 3\ntest = ' + json.dumps(split if full_split else plain)
               + '\nfast_test = ' + json.dumps(split if fast_split else plain) + '\n' + settings)
    repo.write("tests/test_receipts.py", "from pathlib import Path\n"
               "def test_a():\n    Path('a-runs').open('a').write('run\\n')\n"
               "def test_b():\n    Path('b-runs').open('a').write('run\\n')\n"
               "def test_c():\n    Path('c-runs').open('a').write('run\\n')\n")
    repo.write(".gitignore", "a-runs\nb-runs\nc-runs\n.pytest_cache/\n__pycache__/\n")
    synced = repo.forge("sync")
    assert synced.returncode == 0, synced.stdout + synced.stderr
    found = jobs((repo.path / ".github/workflows/forge.yml").read_text("utf-8"))
    pr_count, full_count = (3 if fast_split else 1), (3 if full_split else 1)
    if pr_count == 1:
        assert "strategy:" not in found["tests"]
        assert "FORGE_GROUPS: '1'" in found["tests"]
    else:
        assert "|| '[1, 2, 3]')" in found["tests"]
        assert "&& '1' || '3'" in found["tests"]
    assert f"group: {list(range(1, full_count + 1))}" in found["full-suite"]
    assert f"FORGE_GROUPS: '{full_count}'" in found["full-suite"]
    assert found["tests"].count("::warning::") == int(not fast_split)
    assert found["full-suite"].count("::warning::") == int(fast_split and not full_split)
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure separate client test commands")
    default = repo.git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").removeprefix("origin/")
    repo.git("push", "-q", "origin", "HEAD")
    remote = repo.git("remote", "get-url", "origin")
    repo.git("update-ref", "refs/heads/" + default, "refs/heads/fix/separate-test-groups", cwd=remote)
    # Both commands execute the real suite once across their generated groups.
    for job, mode in (("tests", "--change"), ("full-suite", "--full")):
        value = re.search(r"FORGE_GROUPS: (.+)", found[job])[1]
        count = int(re.search(r"(?:^|\|\| )'(\d+)'", value)[1])
        commands = [json.loads(line) if line.startswith('"') else line
                    for line in re.findall(r"^      - run: (.+)$", found[job], re.M)]
        command = next(line for line in commands if line.startswith("forge test "))
        assert command == "forge test " + mode
        monkeypatch.setenv("FORGE_GROUPS", str(count))
        for group in range(1, count + 1):
            monkeypatch.setenv("FORGE_GROUP", str(group))
            ran = repo.forge(*command.split()[1:])
            assert ran.returncode == 0, ran.stdout + ran.stderr
        for name in ("a-runs", "b-runs", "c-runs"):
            receipt = repo.path / name
            assert receipt.read_text("utf-8") == "run\n"
            receipt.unlink()
