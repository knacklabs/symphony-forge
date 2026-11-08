"""GitHub tests use the runner; laptop tests retain the agent share."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores
from test_close import env  # noqa: F401

STORY = "FIX-CI-TESTS-USE-WHOLE-RUNNER"


@pytest.mark.parametrize("adopted,actions,expected,options", [
    (False, "true", 4, "-n auto"), (False, "false", 1, "-n auto"),
    (True, "true", 4, "-n auto"), (False, "true", 1, ""),
    (False, "true", 2, "-n 2"), (False, "true", 1, "-n auto --maxprocesses=1"),
], ids=["github-new", "laptop", "github-earlier-adopted", "serial", "fixed", "capped"])
def test_1_github_uses_all_cores_and_laptop_keeps_agent_share(repo, gh, monkeypatch, adopted, actions, expected, options):
    # Real pytest workers receive the budget. The old CI reserve starts one
    # worker instead of four. Existing cap tests cover only laptops. OS readings
    # use the existing launcher helper, with no production test seam.
    repo.write("tests/test_budget.py", "# app.py\ndef test_workers(request):\n"
               f"    assert getattr(request.config, 'workerinput', {{'workercount': 1}})['workercount'] == {expected}\n")
    repo.write("app.py", "VALUE = 1\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure client tests")
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path,
                        dirs_exist_ok=True)
        old = (repo.path / "forge.toml").read_text("utf-8")
        repo.git("add", "-A")
        repo.git("commit", "-qm", "Adopt the earlier release")
        repo.git("checkout", "-qb", "fix/client-budget")
        version = repo.forge("--version").stdout.split()[-1]
        repo.write("forge.toml", old.replace('version = "v1.2.2"', f'version = "{version}"'))
        synced = repo.forge("sync")
        assert synced.returncode == 0, synced.stdout + synced.stderr
    else:
        repo.git("checkout", "--orphan", "fresh")
        gh.respond("api", stderr="Branch not protected", exit=1)
        gh.respond("api", "--method", "PUT", stdout="{}")
        initialized = repo.forge("init", "--actions", "yes")
        assert initialized.returncode == 0, initialized.stdout + initialized.stderr
    machine_cores(repo, 4, system_count=12)
    shim = repo.bin / "forge"
    shim.write_text(shim.read_text("utf-8").replace("machine.busy_runners = lambda: 0",
                                                  "machine.busy_runners = lambda: 1"), "utf-8")
    monkeypatch.setenv("GITHUB_ACTIONS", actions)
    monkeypatch.setenv("PYTHONPATH", str(repo.bin))
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q {options}'
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r"(?m)^test = .*", lambda _: "test = " + json.dumps(command), settings))
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("app.py", "VALUE = 2\n")
    result = (repo.forge("test", "--change") if not adopted and actions == "true"
              else repo.forge("test", "--pytest", base))
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Test selection: {expected} workers." in result.stdout


def test_2_github_worker_passes_all_cores_to_its_test_command(env, monkeypatch):
    # A real work turn adds a child-process budget which direct picker cases
    # cannot reach. Fake only the provider; its child runs Forge and real pytest.
    repo = env.repo
    machine_cores(repo, 4)
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    settings = (repo.path / "forge.toml").read_text("utf-8")
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q -n auto'
    env.commit(repo.path, "forge.toml", 'test = ' + json.dumps(command) + '\n' + settings)
    repo.git("push", "-q", "origin", "main")
    item, _ = env.start_fix({"tests/test_budget.py":
        "def test_workers(request):\n    assert request.config.workerinput['workercount'] == 4\n"})
    report = repo.bin / "worker-tests.txt"
    sdk = repo.bin / "claude_agent_sdk/__init__.py"
    action = ("    import subprocess\n"
              f"    result = subprocess.run([{Path(sys.executable).as_posix()!r}, {(repo.bin / 'forge').as_posix()!r}, 'test'], "
              "cwd=options.cwd, capture_output=True, text=True)\n"
              f"    Path({report.as_posix()!r}).write_text(result.stdout + result.stderr, encoding='utf-8')\n"
              "    assert result.returncode == 0, result.stdout + result.stderr\n")
    sdk.write_text(sdk.read_text("utf-8").replace(
        '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)',
        action + '    yield AssistantMessage([TextBlock("SDK worker output")], options.model)'), "utf-8")
    worked = repo.forge("work", item)
    assert worked.returncode == 0, worked.stdout + worked.stderr
    assert "Test selection: 4 workers." in report.read_text("utf-8")
