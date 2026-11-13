"""Forge's Python picker selects a test that imports a changed file of an app in a sub-folder."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.platform

STORY = "FIX-REVIEW-FINDINGS-SPLIT-FROM-A-REPO-S-OWN"
ROOT = Path(__file__).resolve().parents[1]

TEST = ("import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).parents[1]))\nimport app.core.config\n\n\n"
        "def test_it():\n    assert True\n")


@pytest.mark.parametrize("marker", ["pyproject.toml", "setup.py"],
                         ids=["new repo", "earlier-adopted repo"])
def test_1_a_changed_nested_app_file_selects_its_own_apps_importing_test(repo, marker):
    repo.write("forge.toml", "test = " + json.dumps(
        shlex.join([Path(sys.executable).as_posix(), "-m", "pytest", "-q", "apps"])) + "\n")
    for app in ("api", "worker"):
        repo.write(f"apps/{app}/{marker}", "")
        repo.write(f"apps/{app}/app/core/config.py", "# Before\n")
        repo.write(f"apps/{app}/tests/test_{app}_config.py", TEST)
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Two apps")
    base = repo.git("rev-parse", "HEAD").strip()
    repo.write("apps/api/app/core/config.py", "# After\n")
    repo.git("add", "-A")
    repo.git("commit", "-q", "-m", "Change api config")

    result = subprocess.run(
        [sys.executable, str(repo.bin / "forge"), "test", "--pytest", base], cwd=repo.path,
        env={**{k: v for k, v in os.environ.items() if k != "PYTEST_PLUGINS"},
             "PYTHONPATH": str(ROOT / "src")}, capture_output=True, text=True, timeout=120)

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.splitlines()[0] == "Related tests: apps/api/tests/test_api_config.py"
