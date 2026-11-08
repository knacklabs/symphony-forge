"""GitHub tests use the runner; laptop tests retain the agent share."""
import json
import re
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT, machine_cores

STORY = "FIX-CI-TESTS-USE-WHOLE-RUNNER"


@pytest.mark.parametrize("adopted,actions,expected", [
    (False, "true", 4), (False, "false", 1), (True, "true", 4),
], ids=["github-new", "laptop", "github-earlier-adopted"])
def test_1_github_uses_all_cores_and_laptop_keeps_agent_share(repo, gh, monkeypatch, adopted, actions, expected):
    # Real pytest workers receive the budget. The old CI reserve starts one
    # worker instead of four. Existing cap tests cover only laptops. OS readings
    # use the existing launcher helper, with no production test seam.
    repo.write("tests/test_budget.py", "# app.py\ndef test_workers(request):\n"
               f"    assert request.config.workerinput['workercount'] == {expected}\n")
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
    command = f'"{Path(sys.executable).as_posix()}" -m pytest tests -q -n auto'
    settings = (repo.path / "forge.toml").read_text("utf-8")
    repo.write("forge.toml", re.sub(r"(?m)^test = .*", lambda _: "test = " + json.dumps(command), settings))
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("app.py", "VALUE = 2\n")
    result = (repo.forge("test", "--change") if not adopted and actions == "true"
              else repo.forge("test", "--pytest", base))
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"Test selection: {expected} workers." in result.stdout
