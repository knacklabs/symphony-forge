"""Full-run output identifies the configured command before its result.

Test-audit: Removing command disclosure makes a short test look like whole-suite
proof. Existing full-run coverage checks execution and status, not this output.
Run the real command on new and earlier-adopted repos; only GitHub is fake.
No production seam is needed.
"""
import json
import shutil
import sys
from pathlib import Path

import pytest

from conftest import ROOT

STORY = "full-run-names-its-command"


@pytest.mark.parametrize("adopted", [False, True], ids=["new-client", "earlier-adoption"])
def test_1_full_run_prints_exact_command_before_result(repo, gh, monkeypatch, adopted):
    if adopted:
        shutil.copytree(ROOT / "tests/fixtures/adopted-v1.2.2/client", repo.path, dirs_exist_ok=True)
    version = repo.forge("--version").stdout.split()[-1]
    command = f'"{Path(sys.executable).as_posix()}" -m pytest "short tests" -q'
    repo.write("forge.toml", f'version = "{version}"\nrepo = "forge-source"\n'
               'checks = []\n' + f'test = {json.dumps(command)}\n')
    repo.write("short tests/test_short.py", "def test_short():\n    assert 2 + 2 == 4\n")
    repo.write(".gitignore", "__pycache__/\n.pytest_cache/\n")
    repo.git("add", "-A")
    repo.git("commit", "-qm", "Configure a short test command")
    repo.git("push", "-q", "origin", "main")
    monkeypatch.delenv("PYTEST_ADDOPTS", raising=False)
    monkeypatch.delenv("FORGE_GROUP", raising=False)
    monkeypatch.delenv("FORGE_GROUPS", raising=False)
    gh.respond("api", "--method", "POST", stdout="{}")

    full = repo.forge("test", "--full")

    assert full.returncode == 0, full.stdout + full.stderr
    line = f"Full run command: {command}\n"
    assert line in full.stdout, full.stdout
    assert full.stdout.index(line) < full.stdout.index("1 passed"), full.stdout
