"""Direct commands and fixed shard counts keep the full matrix.

Test-audit: Runs the synced CI script on real commits and evaluates its workflow.
The existing test-only cases cannot detect shared-input or fixed-shard mistakes.
No fake or production seam decides selection.
Fixed shard counts must keep all groups: the old cases use Forge's pytest split
and cannot catch omitted shards in a client's own command.
Mixed suites protect the same contract when a dynamic count masks a fixed count
elsewhere in the command. The owner now requires an explicit {groups} count.
"""
import os
import re
import subprocess
import sys

import pytest

from test_ci_limits_pull_requests_to_linux import expression
from test_groups_pytest import PYTEST, _branch, _new_client, _settings
from test_merged_default_branch_pull_requests_run_normal_groups import _commit
from test_testplace_workflow import _jobs

STORY = "FORGE-CITIME-1"


@pytest.mark.parametrize("fixed_shards,fast_test", [
    (False, PYTEST + " --splits {groups} --group {group}"),
    (True, "vitest run --shard={group}/4"),
    (True, "vitest run --shard={group}/{groups} && vitest run --shard={group}/4"),
], ids=["dynamic-count", "fixed-shards", "mixed-suites"])
def test_2_direct_and_fixed_commands_keep_configured_groups(repo, gh, tmp_path, fixed_shards, fast_test):
    client = _new_client(repo, gh, tmp_path, "client")
    _branch(repo, client, "small-change")
    _settings(client, test=PYTEST, groups=4 if fixed_shards else 2,
              fast_test=fast_test)
    (client / "tests").mkdir(exist_ok=True)
    (client / "tests/test_example.py").write_text("def test_it(): assert True\n", encoding="utf-8")
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Set up", cwd=client)
    synced = repo.forge("sync", cwd=client)
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.git("add", "-A", cwd=client)
    repo.git("commit", "-qm", "Sync", "--allow-empty", cwd=client)
    base = repo.git("rev-parse", "HEAD", cwd=client)
    workflow = (client / ".github/workflows/forge.yml").read_text("utf-8")
    excludes = re.search(r"^          DOCS_ONLY_EXCLUDES: '(.*)'$", workflow, re.M)[1]
    matrix = re.search(r"^        group: (.+)$", _jobs(workflow)["tests"], re.M)[1]
    matrix = matrix.replace("needs.docs-check.outputs.one-group", "github.one_group")
    matrix = matrix.replace("needs.docs-check.outputs.test-only", "github.test_only")
    group_output = re.search(r"^      one-group: (.+)$", _jobs(workflow)["docs-check"], re.M)[1]
    group_output = group_output.replace("steps.docs.outputs.one-group", "github.one_group")
    code = {f"src/file_{i}.py": "VALUE = 1\n" for i in range(6)}
    small = dict(list(code.items())[:3])
    # These fast commands run the configured suite rather than the related selection.
    cases = [(small, [1, 2]), (dict(list(code.items())[:5]), [1, 2]), (code, [1, 2])]
    for shared in ("pnpm-lock.yaml", "tsconfig.json", "tests/conftest.py",
                   ".forge/review-tests.py", ".github/workflows/other.yml"):
        source = (client / shared).read_text("utf-8") if (client / shared).is_file() else ""
        cases.append(({"src/one.py": "VALUE = 1\n", shared: source + "\n# Changed\n"}, [1, 2]))
    script = (client / ".forge/review-tests.py").read_text("utf-8")
    cases.append(({"tests/test_example.py": "def test_it(): assert 1\n",
                   ".forge/review-tests.py": script + "\n# Changed\n"}, [1, 2]))
    cases.append(({**small, "README.md": "Changed\n",
                   "tests/test_example.py": "def test_it(): assert 1\n"}, [1, 2]))
    if fixed_shards:
        cases = [(small, [1, 2, 3, 4])]
    for files, expected in cases:
        head = _commit(repo, client, tmp_path, [base], files)
        repo.git("checkout", "-q", "--detach", head, cwd=client)
        output = tmp_path / "outputs"
        output.write_text("", encoding="utf-8")
        done = subprocess.run([sys.executable, ".forge/review-tests.py"], cwd=client,
                              env={**os.environ, "BASE_SHA": base, "HEAD_SHA": head,
                                   "DOCS_ONLY_EXCLUDES": excludes, "GITHUB_OUTPUT": str(output)},
                              capture_output=True, text=True, timeout=30)
        assert done.returncode == 0, done.stdout + done.stderr
        values = dict(line.split("=", 1) for line in output.read_text("utf-8").splitlines())
        one_group = expression(group_output, one_group=values["one-group"])
        assert expression(matrix, one_group=one_group,
                          test_only=values["test-only"]) == expected, (files, values)
