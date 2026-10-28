"""Groups reach generated CI and the runner through Forge's real commands.

Test-audit gate: these three command contracts protect workflow generation and
validation, argument substitution at each execution path, and isolated cached
passes. Missing substitution or a shared cache key is a credible regression;
existing tests have no group inputs. The runner records only its external argv
and fails a specified shard, so Forge owns all behavior under assertion. No
test-only production seam is needed.
"""
import json
import os
import re
import shutil
import sys
from pathlib import Path

import pytest

from test_node_test_worker_budget import client
from test_testplace_workflow import _jobs

STORY = "FORGE-GROUPS-1/ANYRUNNER"


@pytest.fixture(params=[False, True], ids=["new", "earlier-adopted"])
def grouped_client(repo, gh, monkeypatch, tmp_path, request):
    client(repo, gh, request.param)
    repo.git("checkout", "-qb", "fix/groups")
    repo.write(".factory/fixes/groups.json", json.dumps({
        "kind": "fix", "branch": "fix/groups", "why": "Group client tests",
        "done_when": "Tests run in groups", "status": "started"}))
    settings = (repo.path / "forge.toml").read_text("utf-8")
    settings = re.sub(r"^(test|fast_test|groups) = .*\n", "", settings, flags=re.M)
    settings = 'groups = 3\ntest = "vitest run --shard={group}/{groups}"\n' + settings
    repo.write("forge.toml", settings)
    node = shutil.which("node")
    assert node, "The runner argument contract requires Node.js"
    runner = repo.write("node_modules/.bin/vitest", f"#!{Path(node).as_posix()}\n"
        "const fs = require('node:fs'); const args = process.argv.slice(2);\n"
        "fs.appendFileSync(process.env.GROUP_RECEIPT, JSON.stringify(args) + '\\n');\n"
        "if (args.includes('--shard=2/2')) process.exit(17);\n")
    runner.chmod(0o755)
    if sys.platform == "win32":
        repo.write("node_modules/.bin/vitest.cmd", f'@"{Path(node).as_posix()}" "%~dp0vitest" %*\n')
    monkeypatch.setenv("PATH", str(runner.parent) + os.pathsep + os.environ["PATH"])
    receipt = tmp_path / "runner-arguments.jsonl"
    monkeypatch.setenv("GROUP_RECEIPT", str(receipt))
    monkeypatch.delenv("FORGE_GROUP", raising=False)
    monkeypatch.delenv("FORGE_GROUPS", raising=False)
    synced = repo.forge("sync")
    # Sync must accept the setting before the runtime contracts can be exercised.
    assert synced.returncode == 0, synced.stdout + synced.stderr
    repo.write("app.js", "const value = 1;\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure grouped client tests")
    base = repo.git("rev-parse", "HEAD")
    repo.git("update-ref", repo.git("symbolic-ref", "refs/remotes/origin/HEAD"), base)
    repo.write("app.js", "const value = 2;\n")
    repo.git("add", "app.js")
    repo.git("commit", "-qm", "Change the client source")
    return repo, receipt, settings, base


@pytest.mark.platform
def test_1_groups_split_the_test_job(grouped_client):
    repo, _, settings, _ = grouped_client
    workflow = (repo.path / ".github/workflows/forge.yml").read_text("utf-8")
    job = _jobs(workflow)["tests"]
    assert "group: [1, 2, 3]" in job
    assert "of 3" in job
    assert "FORGE_GROUP: ${{ matrix.group }}" in job
    assert "FORGE_GROUPS: '3'" in job
    assert 'run: "forge test --change"' in job
    assert "--splits" not in job and "--collect-only" not in job
    doctor = repo.forge("doctor")
    assert "does not run forge test --change" not in doctor.stdout + doctor.stderr
    assert "workflow" not in "\n".join(
        line for line in (doctor.stdout + doctor.stderr).splitlines() if "Fix:" in line)
    for value in ("0", "true", '"3"'):
        repo.write("forge.toml", settings.replace("groups = 3", "groups = " + value))
        refused = repo.forge("test")
        assert refused.returncode != 0
        assert "groups must be a whole number of 1 or more" in refused.stdout + refused.stderr


@pytest.mark.platform
def test_2_test_command_gets_group_numbers(grouped_client, monkeypatch):
    repo, receipt, settings, base = grouped_client
    monkeypatch.setenv("FORGE_GROUP", "2")
    monkeypatch.setenv("FORGE_GROUPS", "3")
    changed = repo.forge("test", "--change")
    assert changed.returncode == 0, changed.stdout + changed.stderr
    args = json.loads(receipt.read_text("utf-8").splitlines()[-1])
    assert "--shard=2/3" in args and "--passWithNoTests" in args
    assert args[args.index("--changed") + 1] == base
    monkeypatch.delenv("FORGE_GROUP")
    monkeypatch.delenv("FORGE_GROUPS")
    laptop = repo.forge("test")
    assert laptop.returncode == 0, laptop.stdout + laptop.stderr
    assert "--shard=1/1" in json.loads(receipt.read_text("utf-8").splitlines()[-1])
    repo.write("forge.toml", 'fast_test = "vitest run --shard={group}/{groups}"\n' + settings)
    monkeypatch.setenv("FORGE_GROUP", "2")
    monkeypatch.setenv("FORGE_GROUPS", "3")
    direct = repo.forge("test", "--change")
    assert direct.returncode == 0, direct.stdout + direct.stderr
    assert "--shard=2/3" in json.loads(receipt.read_text("utf-8").splitlines()[-1])
    # The explicit pytest entry reads raw test separately from close and direct fast_test.
    repo.write("tests/test_numbers.py", "def test_numbers(pytestconfig):\n"
               "    assert pytestconfig.getini('cache_dir') == '2/3'\n")
    command = (json.dumps(Path(sys.executable).as_posix()) +
               " -m pytest tests/test_numbers.py -q -o cache_dir={group}/{groups}")
    repo.write("forge.toml", re.sub(r"^test = .*", lambda _: "test = " + json.dumps(command),
                                  settings, flags=re.M))
    monkeypatch.setenv("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
    explicit = repo.forge("test", "--pytest", base)
    assert explicit.returncode == 0, explicit.stdout + explicit.stderr
    assert "1 passed" in explicit.stdout


@pytest.mark.platform
def test_4_groups_never_reuse_another_groups_pass(grouped_client, monkeypatch):
    repo, receipt, _, _ = grouped_client
    assert repo.git("status", "--porcelain") == ""
    monkeypatch.setenv("FORGE_GROUP", "1")
    monkeypatch.setenv("FORGE_GROUPS", "2")
    first = repo.forge("test", "--change")
    assert first.returncode == 0, first.stdout + first.stderr
    before = receipt.read_text("utf-8")
    repeated = repo.forge("test", "--change")
    assert repeated.returncode == 0, repeated.stdout + repeated.stderr
    assert "already passed" in repeated.stdout
    assert receipt.read_text("utf-8") == before
    monkeypatch.setenv("FORGE_GROUP", "2")
    other = repo.forge("test", "--change")
    assert other.returncode != 0, other.stdout + other.stderr
    assert "already passed" not in other.stdout
    assert "--shard=2/2" in json.loads(receipt.read_text("utf-8").splitlines()[-1])
